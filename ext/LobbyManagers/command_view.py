
from io import BytesIO
from discord import app_commands, ui, ButtonStyle, Interaction
from ..InjusticeJudge.commands import _parse, _injustice, _skill

class CommandSuggestionView(ui.View):
    def __init__(self, link: str, 
                       original_interaction: Interaction,
                       parse_enabled: bool = True,
                       injustice_enabled: bool = True,
                       skill_enabled: bool = True,
                       timeout: float = 60):
        super().__init__(timeout = timeout)
        self.link = link
        self.original_interaction = original_interaction
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

    async def on_timeout(self):
        await self.remove_view()

    async def remove_view(self):
        await self.original_interaction.edit_original_response(view=None)
        self.stop()
    async def update_view(self):
        if not (self.parse_enabled or self.injustice_enabled or self.skill_enabled):
            await self.remove_view()
        else:
            await self.original_interaction.edit_original_response(view=self)

    @ui.button(label="/parse", style=ButtonStyle.blurple, row=0)
    async def parse_button(self, interaction: Interaction, button: ui.Button):
        await _parse(interaction, self.link, None, True)
        print("parse clicked")
        button.disabled = True
        self.parse_enabled = False
        await self.update_view()

    @ui.button(label="/injustice", style=ButtonStyle.blurple, row=0)
    async def injustice_button(self, interaction: Interaction, button: ui.Button):
        await _injustice(interaction, self.link, {0,1,2,3})
        print("injustice clicked")
        button.disabled = True
        self.injustice_enabled = False
        await self.update_view()

    @ui.button(label="/skill", style=ButtonStyle.blurple, row=0)
    async def skill_button(self, interaction: Interaction, button: ui.Button):
        await _skill(interaction, self.link, {0,1,2,3})
        print("skill clicked")
        button.disabled = True
        self.skill_enabled = False
        await self.update_view()

