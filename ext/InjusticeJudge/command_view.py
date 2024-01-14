from discord import app_commands, ui, ButtonStyle, Interaction, Message, WebhookMessage
from .commands import _parse, _injustice, _skill

class CommandSuggestionView(ui.View):
    def __init__(self, link: str, 
                       parse_enabled: bool = True,
                       injustice_enabled: bool = True,
                       skill_enabled: bool = True,
                       timeout: float = 60) -> None:
        super().__init__(timeout = timeout)
        self.link = link
        self.parse_enabled = parse_enabled
        self.injustice_enabled = injustice_enabled
        self.skill_enabled = skill_enabled
        for child in self.children:
            if type(child) == ui.Button:
                if child.label == "/parse" and not parse_enabled:
                    self.remove_item(child)
                elif child.label == "/injustice" and not injustice_enabled:
                    self.remove_item(child)
                elif child.label == "/skill" and not skill_enabled:
                    self.remove_item(child)
    def set_message(self, message: Message) -> None:
        self.message = message

    async def on_timeout(self) -> None:
        await self.remove_view()

    async def remove_view(self) -> None:
        await self.message.edit(view=None)
        self.stop()

    async def update_view(self) -> None:
        if not (self.parse_enabled or self.injustice_enabled or self.skill_enabled):
            await self.remove_view()
        else:
            if isinstance(self.message, WebhookMessage):
                await self.message.edit(view=self)
            else:
                await self.message.edit(view=self, suppress=True)

    @ui.button(label="/parse", style=ButtonStyle.blurple, row=0)
    async def parse_button(self, interaction: Interaction, button: ui.Button) -> None:
        await interaction.response.defer()
        await _parse(interaction, self.link, None, True)
        print("parse clicked")
        button.disabled = True
        self.parse_enabled = False
        await self.update_view()

    @ui.button(label="/injustice", style=ButtonStyle.blurple, row=0)
    async def injustice_button(self, interaction: Interaction, button: ui.Button) -> None:
        await interaction.response.defer()
        await _injustice(interaction, self.link, {0,1,2,3})
        print("injustice clicked")
        button.disabled = True
        self.injustice_enabled = False
        await self.update_view()

    @ui.button(label="/skill", style=ButtonStyle.blurple, row=0)
    async def skill_button(self, interaction: Interaction, button: ui.Button) -> None:
        await interaction.response.defer()
        await _skill(interaction, self.link, {0,1,2,3})
        print("skill clicked")
        button.disabled = True
        self.skill_enabled = False
        await self.update_view()

