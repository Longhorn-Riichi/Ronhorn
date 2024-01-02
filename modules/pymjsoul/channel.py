import asyncio
from typing import Optional

import websockets
import logging

import google.protobuf as pb
from .errors import ERRORS

MSG_TYPE_NOTIFY = 1
MSG_TYPE_REQUEST = 2
MSG_TYPE_RESPONSE = 3

MAX_MSG_INDEX = 2**16

class MethodNotFoundError(Exception):
    def __init__(self, methodName, moduleName):
        self.message = f"No method named '{methodName}' in module '{moduleName}'"
        super().__init__(self.message)

class ResponseTimeoutError(Exception):
    def __init__(self, timeoutDuration):
        self.message = f"Response not received within specified timeout duration ({timeoutDuration}s)"
        super().__init__(self.message)

class GeneralMajsoulError(Exception):
    def __init__(self, errorCode: int, message: str):
        self.errorCode = errorCode
        self.message = f"ERROR CODE {errorCode}: {message}"
        super().__init__(self.message)

class MajsoulChannel():
    _RESPONSE_TIMEOUT_DURATION = 10

    def __init__(self, proto, log_messages=True, logger_name="MajsoulChannel"):
        self.logger = logging.getLogger(logger_name)
        
        self.index = 0 # should be referenced while holding the lock
        self.websocket = None
        self.websocket_lock = asyncio.Lock()

        self.uri = None

        self.proto = proto
        self.requests = {}
        self.responses = {}

        self._subscriptions = {}
        self._subscriptions_lock = asyncio.Lock()

        self.MostRecentNotify = None
        self.log_messages = log_messages

        self.sustain_task: Optional[asyncio.Task] = None
        self.listen_task: Optional[asyncio.Task] = None
        self.eventloop_task: Optional[asyncio.Task] = None
    
    async def clean_up(self):
        """
        close the connection, kill the asyncio tasks and reset the variables
        (except self.uri and the subscriptions).
        This prepares for starting another connection with `self.connect()`
        while keeping the same subscriptions.
        """
        self.sustain_task.cancel()
        self.listen_task.cancel()
        self.eventloop_task.cancel()

        self.index = 0
        self.requests = {}
        self.responses = {}
        
        self.MostRecentNotify = None
        self.Notifications = asyncio.Queue()

        await self.close() # lock?

    async def reconnect(self):
        """
        calls `self.clean_up()` and reconnect with the existing `self.uri`
        """
        await self.clean_up()
        await self.connect(self.uri)

    async def connect(self, uri):
        self.uri = uri

        self.Notifications = asyncio.Queue()
        self.websocket = await websockets.connect(self.uri, open_timeout=None, close_timeout=None)

        self.logger.info(f'Connected to {self.uri}')

        self.sustain_task = asyncio.create_task(self.sustain())
        self.listen_task = asyncio.create_task(self.listen())
        self.eventloop_task = asyncio.create_task(self.eventloop())

    async def sustain(self, ping_interval=3):
        '''
        Looping coroutine that keeps the connection to the server alive.
        '''
        try:
            while self.websocket.open:
                await self.websocket.ping()
                await asyncio.sleep(ping_interval)
        except asyncio.CancelledError:
            self.logger.info("`sustain` task cancelled")
        except Exception as e:
            self.logger.info(f"Exception occurred in `sustain` task: {e}")

    async def subscribe(self, name, cb):
        async with self._subscriptions_lock:
            if name in self._subscriptions:
                self._subscriptions[name].append(cb)
            else:
                self._subscriptions[name] = [cb]

    async def eventloop(self):
        ''' Event loop running as a separate coroutine to listen(), otherwise we can run into deadlock. '''
        try:
            while True:
                name, msg = await self.Notifications.get()
                if name in self._subscriptions:
                    for sub_callback in self._subscriptions[name]:
                        await sub_callback(name, msg)
                else:
                    logging.debug(f"Notification for {name} had no subscribers.")
        except asyncio.CancelledError:
            self.logger.info("`eventloop` task cancelled")
        except Exception as e:
            self.logger.info(f"Exception occurred in `eventloop` task: {e}")

    async def listen(self):
        '''
        Looping coroutine that receives messages from the server.
        '''
        try:
            async for message in self.websocket:
                msgType = int.from_bytes(message[0:1], 'little')

                if msgType == MSG_TYPE_NOTIFY:
                    msgPayload = message[1:]
                    name, data = self.unwrap(msgPayload)

                    name = name.strip(f'.{self.proto.DESCRIPTOR.package}')

                    try:
                        msgDescriptor = self.message_lookup(name)
                    except KeyError as e:
                        logging.error(e)
                        continue

                    msgClass = pb.reflection.MakeClass(msgDescriptor)

                    msg = msgClass()
                    msg.ParseFromString(data)

                    # Duplicate notifications can be received next to each other.
                    # Never process the same message twice.
                    if (name, msg) != self.MostRecentNotify:
                        if self.log_messages:
                            self.logger.info("Notification received.\nname\nmsg")
                        self.MostRecentNotify = (name, msg)

                        await self.Notifications.put((name, msg))
                elif msgType == MSG_TYPE_RESPONSE:
                    if self.log_messages:
                        self.logger.info("Response received.")
                    msgIndex = int.from_bytes(message[1:3], 'little')
                    msgPayload = message[3:]

                    if msgIndex in self.requests:
                        name, data = self.unwrap(msgPayload)
                        self.responses[msgIndex] = data

                        resEvent = self.requests[msgIndex]
                        resEvent.set()
        except asyncio.CancelledError:
            self.logger.info("`listen` task cancelled")
        except Exception as e:
            self.logger.info(f"Exception occurred in `listen` task: {e}")

    async def close(self):
        await self.websocket.close()

    async def send(self, name:str, data:bytes):
        '''
        Sends a message/request to the server.

        Param:
            name : str
                Full name of the protobuf message to be sent. Example: ".lq.Lobby.oauth2Login:"

            data : bytes
                Message payload to be sent. This needs to be a byte string. After creating a protobuf message 'msg'
                you can call msg.SerializeToString() and pass it in as this parameter.

        Info:
            The messages that are sent/received are formatted differently depending on the type of message (notify/request/response).

            REQUEST/RESPONSE

            Byte #:     0       1       2       3       4       5     .... and so on
                     ___|___ ___|___ ___|___ ___|___ ___|___ ___|___
                    |       |               |
                    | MSG   |    MESSAGE    |      MESSAGE            ....
                    | TYPE  |     INDEX     |      PAYLOAD            .... rest of the message
                    |_______|_______ _______|_______ _______ _______

            NOTIFY:

            Byte #:     0       1       2    .... and so on
                     ___|___ ___|___ ___|___
                    |       |
                    | MSG   |    MESSAGE     ....
                    | TYPE  |    PAYLOAD     .... rest of the message
                    |_______|_______ _______
        '''

        wrapped = self.wrap(name, data)
        async with self.websocket_lock:
            msgIndex = self.index
            self.index = (self.index + 1) % MAX_MSG_INDEX
            message = MSG_TYPE_REQUEST.to_bytes(1, 'little') + msgIndex.to_bytes(2, 'little') + wrapped

            resEvent = asyncio.Event()
            self.requests[msgIndex] = resEvent
            await self.websocket.send(message)

            try:
                await asyncio.wait_for(resEvent.wait(), timeout=self._RESPONSE_TIMEOUT_DURATION)
            except asyncio.TimeoutError:
                del self.requests[msgIndex]
                raise ResponseTimeoutError(self._RESPONSE_TIMEOUT_DURATION)

            res = self.responses[msgIndex]

            del self.responses[msgIndex]
            del self.requests[msgIndex]

            return res

    async def call(self, methodName, **msgFields):
        '''
        Simpler method for sending requests. Looks up the request and processes the fields for you.
        Use this instead of MajsoulChannel.send

        Param:
            methodName : str
                Name of the method to be called (without package name). Example: 'oauth2Login'

            **msgFields : dict
                Fields to be entered into the protobuf message.

        Example Usage:
            res = await self.call(
                methodName = 'oauth2LoginContestManager',
                type = 10,
                access_token = 'YOUR_TOKEN_HERE',
                reconnect = True
            )
        '''
        # Optional method hack
        serviceName = None
        if 'serviceName' in msgFields:
            serviceName = msgFields['serviceName']
            del msgFields['serviceName']

        methodDescriptor = self.method_lookup(methodName, serviceName)

        msgName = f'.{methodDescriptor.full_name}'

        reqMessageClass = pb.reflection.MakeClass(methodDescriptor.input_type)
        reqMessage = reqMessageClass(**msgFields)

        resData = await self.send(msgName, reqMessage.SerializeToString())

        resMessageClass = pb.reflection.MakeClass(methodDescriptor.output_type)
        resMessage = resMessageClass()
        resMessage.ParseFromString(resData)

        if resMessage.error.code:
            raise GeneralMajsoulError(resMessage.error.code, ERRORS.get(resMessage.error.code, 'Unknown error'))

        if self.log_messages:
            self.logger.info(resMessage)

        return resMessage

    def method_lookup(self, methodName, serviceName):
        methodDescriptor = None

        if serviceName:
            serviceDescriptor = self.proto.DESCRIPTOR.services_by_name[serviceName]
            methodDescriptor = serviceDescriptor.FindMethodByName(methodName)
        else:
            for serviceDescriptor in self.proto.DESCRIPTOR.services_by_name.values():
                try:
                    methodDescriptor = serviceDescriptor.FindMethodByName(methodName)
                    break
                except KeyError:
                    continue

        if methodDescriptor == None:
            raise MethodNotFoundError(methodName, self.proto.__name__)

        return methodDescriptor

    def message_lookup(self, messageName):
        return self.proto.DESCRIPTOR.message_types_by_name[messageName]

    def wrap(self, name, data):
        msg = self.proto.Wrapper(name=name, data=data)

        return msg.SerializeToString()

    def unwrap(self, wrapped):
        msg = self.proto.Wrapper()
        msg.ParseFromString(wrapped)

        return msg.name, msg.data

