from discord import app_commands, ui, ButtonStyle, File, Interaction, Message, WebhookMessage
from .commands import _parse, _injustice, _skill
from .utilities import draw_graph, parse_link

class CommandSuggestionView(ui.View):
    def __init__(self, link: str, 
                       score_graph_enabled: bool = True,
                       bonus_graph_enabled: bool = True,
                       parse_enabled: bool = True,
                       injustice_enabled: bool = True,
                       skill_enabled: bool = True,
                       timeout: float = 60) -> None:
        super().__init__(timeout = timeout)
        self.link = link
        self.score_graph_enabled = score_graph_enabled
        self.bonus_graph_enabled = bonus_graph_enabled
        self.parse_enabled = parse_enabled
        self.injustice_enabled = injustice_enabled
        self.skill_enabled = skill_enabled
        for child in self.children:
            if type(child) == ui.Button:
                if child.label == "Graph scores" and not score_graph_enabled:
                    self.remove_item(child)
                if child.label == "Graph placement bonuses" and not bonus_graph_enabled:
                    self.remove_item(child)
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

    @ui.button(label="Graph scores", style=ButtonStyle.blurple, row=0)
    async def score_graph_button(self, interaction: Interaction, button: ui.Button) -> None:
        await interaction.response.defer()
        print("score graph clicked")
        image = await draw_graph(self.link, "Scores only")
        identifier, _ = parse_link(self.link)
        file = File(fp=image, filename=f"game-{identifier}.png")
        await interaction.channel.send(file=file)  # type: ignore[union-attr]
        button.disabled = True
        self.score_graph_enabled = False
        await self.update_view()

    @ui.button(label="Graph placement bonuses", style=ButtonStyle.blurple, row=0)
    async def bonus_graph_button(self, interaction: Interaction, button: ui.Button) -> None:
        await interaction.response.defer()
        print("bonus graph clicked")
        image = await draw_graph(self.link, "Scores with placement bonus")
        identifier, _ = parse_link(self.link)
        file = File(fp=image, filename=f"game-{identifier}.png")
        await interaction.channel.send(file=file)  # type: ignore[union-attr]
        button.disabled = True
        self.bonus_graph_enabled = False
        await self.update_view()

    @ui.button(label="/parse", style=ButtonStyle.blurple, row=1)
    async def parse_button(self, interaction: Interaction, button: ui.Button) -> None:
        await interaction.response.defer()
        print("parse clicked")
        await _parse(interaction, self.link)
        button.disabled = True
        self.parse_enabled = False
        await self.update_view()

    @ui.button(label="/injustice", style=ButtonStyle.blurple, row=1)
    async def injustice_button(self, interaction: Interaction, button: ui.Button) -> None:
        await interaction.response.defer()
        print("injustice clicked")
        await _injustice(interaction, self.link, {0,1,2,3})
        button.disabled = True
        self.injustice_enabled = False
        await self.update_view()

    @ui.button(label="/skill", style=ButtonStyle.blurple, row=1)
    async def skill_button(self, interaction: Interaction, button: ui.Button) -> None:
        await interaction.response.defer()
        print("skill clicked")
        await _skill(interaction, self.link, {0,1,2,3})
        button.disabled = True
        self.skill_enabled = False
        await self.update_view()

