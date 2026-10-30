"""Prepare the Lantern UI as an explicitly branded Atlas edition with private settings."""
from pathlib import Path
import argparse, hashlib, json, shutil
from prepare_lantern import replace, apply_patch, REPO, NATIVEPLUS

def prepare(root:Path):
    app=root/'launcher/windows/BloodborneLauncher'
    proof={}
    def edit(name,fn):
        path=app/name;before=hashlib.sha256(path.read_bytes()).hexdigest()
        path.write_text(fn(path.read_text(encoding='utf-8-sig')),encoding='utf-8',newline='\n')
        proof[name]={'before':before,'after':hashlib.sha256(path.read_bytes()).hexdigest()}
    # Native+ HDR's display page, peak detection and choices only: Atlas keeps its own
    # identity, settings folder and update policy. Atlas edits none of these files.
    prefix='launcher/windows/BloodborneLauncher/'
    for name,sides in apply_patch(root,NATIVEPLUS/'nativeplus-launcher.patch').items():
        if not name.startswith(prefix):raise ValueError('Native+ launcher patch outside the Windows launcher: '+name)
        proof[name[len(prefix):]]=sides
    shutil.copy2(REPO/'source/launchers/AtlasIntegration.cs',app/'Core/AtlasIntegration.cs')
    edit('Core/Paths.cs',lambda s:replace(replace(s,'public static readonly string ConfigDir = MigratedConfigDir();',
        'public static readonly string ConfigDir = AtlasIntegration.ConfigDirectory();'),
        'public static string PortDir { get; set; } = "";',
        'public static string PortDir { get => AtlasIntegration.Root; set { /* Fixed to this complete Atlas package. */ } }'))
    def runner(s):
        s=replace(s,'public static bool Custom(LauncherSettings s) => s.Str("launch_method") == "custom";',
            'public static bool Custom(LauncherSettings s) => false;')
        return replace(s,'            foreach (var (key, value) in GameEnvironment.Build(s))\n                info.Environment[key] = value;',
            '            try { foreach (var (key, value) in GameEnvironment.Build(s)) info.Environment[key] = value; }\n'
            '            catch (Exception e) when (e is IOException or InvalidOperationException or System.Text.Json.JsonException) { return e.Message; }')
    edit('Core/GameRunner.cs',runner)
    # SDL's DirectInput scan waits on every HID device: one that stops answering held the
    # Controls page (SDL_InitSubSystem on the UI thread) for 30 s. The Native+ engine already
    # turns it off; the launcher's pad detection and the game's environment now do too.
    edit('Core/GameEnvironment.cs',lambda s:replace(replace(s,'            return env;\n',
        '            AtlasIntegration.Apply(s, env);\n            return env;\n'),
        '            yield return ("SDL_JOYSTICK_HIDAPI_PS3", "1");\n',
        '            yield return ("SDL_JOYSTICK_DIRECTINPUT", "0");\n'
        '            yield return ("SDL_JOYSTICK_HIDAPI_PS3", "1");\n'))
    edit('Core/LauncherSettings.cs',lambda s:replace(s,'            ["ui_language"] = "en",',
        '            ["atlas_enabled"] = true,\n            ["atlas_travel_enabled"] = true,\n'
        '            ["atlas_npc_mode"] = "all",\n            ["atlas_items_enabled"] = false,\n'
        '            ["atlas_fog_enabled"] = false,\n            ["ui_language"] = "en",').replace(
        '["check_updates"] = true','["check_updates"] = false'))
    # A vanilla upstream update would remove the map hooks. Both update entry points refuse it.
    def updater(s):
        s=replace(s,'public const string EngineId = "lantern-fps94";',
            'public const string EngineId = "lantern-fps94-atlas-3.1";')
        s=replace(s,'public const string ExeName = "Lantern Engine.exe";',
            'public const string ExeName = "HuntersAtlas.exe";')
        s=replace(s,'public const string OldExeName = "Bloodborne Launcher.exe";',
            'public const string OldExeName = "HuntersAtlas-Previous.exe";')
        for signature,result in [('public static async Task<Release?> LatestAsync(bool beta = false)','null'),
                ('public static async Task<IReadOnlyList<Release>> AllAsync()','Array.Empty<Release>()')]:
            s=replace(s,signature+'\n        {',signature+'\n        {\n'
                '            if (AtlasIntegration.ProtectRuntimeUpdates) { await Task.CompletedTask; return '+result+'; }')
        signature='public static async Task<IReadOnlyList<string>> InstallAsync(Release release, bool package, IProgress<double>? progress = null)'
        s=replace(s,signature+'\n        {',signature+'\n        {\n'
            '            if (AtlasIntegration.ProtectRuntimeUpdates) throw new InvalidOperationException("Install Atlas updates from the complete matching Atlas ZIP. Stock engine updates cannot be installed over this modified runtime.");')
        s=replace(s,'public static string CurrentLabel => Label(Current, CurrentBeta);',
            'public static string CurrentLabel => "Atlas 3.1 + Native+ HDR (based on Lantern 0.9.37)";')
        return s
    edit('Core/Updater.cs',updater)
    edit('App.xaml.cs',lambda s:replace(s,'if (Core.LanternRename.Run(e.Args))','if (Core.AtlasIntegration.AllowLegacyRename && Core.LanternRename.Run(e.Args))'))
    edit('MainWindow.xaml',lambda s:s.replace('Title="Lantern Engine"','Title="Hunter\'s Atlas — based on Lantern Engine"'))
    def main_window(s):
        s=s.replace('Lantern Engine ready.',"Hunter's Atlas ready (modified Lantern-based runtime).")
        s=replace(s,'            if (_directPlay)\n                WindowState = WindowState.Minimized;',
            '            if (_directPlay)\n                ShowActivated = false;')
        s=replace(s,'            InitializeComponent();','            AtlasIntegration.Trace("window: initialize");\n            InitializeComponent();')
        s=replace(s,'            ws.Initialise();','            ws.Initialise();\n            AtlasIntegration.Trace("workspace: initialized");')
        s=replace(s,'                Updater.CleanUp();','                AtlasIntegration.Trace("window: loaded");\n                Updater.CleanUp();')
        return replace(s,'            await PlayOrStopAsync();','            AtlasIntegration.Trace("direct play: start");\n            await PlayOrStopAsync();',count=1)
    edit('MainWindow.xaml.cs',main_window)
    def settings(s):
        anchor='            Group(L.T("Appearance"));'
        page='''            Group("Hunter's Atlas 3.1");
            Body.Children.Add(new TextBlock { Text = AtlasIntegration.Credit + "\\n" + AtlasIntegration.NativePlusCredit + "\\n" + AtlasIntegration.Modified,
                TextWrapping = TextWrapping.Wrap, Margin = new Thickness(14, 4, 14, 12) });
            SettingToggle(SymbolRegular.Map24, "Enable Hunter's Atlas", "Press M in game. Changes apply on the next game launch.", "atlas_enabled");
            SettingToggle(SymbolRegular.Map24, "Discovered-lamp travel", "Use the game's normal travel system for eligible, discovered destinations.", "atlas_travel_enabled");
            SettingToggle(SymbolRegular.Map24, "Item markers", "Show supported item categories on the map.", "atlas_items_enabled");
            SettingToggle(SymbolRegular.Map24, "Fog of exploration", "Track exploration for this profile.", "atlas_fog_enabled");
            ComboRow(SymbolRegular.Map24, "NPC markers", "Choose which NPC markers are shown.",
                new[] { new Choice("All", "all"), new Choice("New dialogue", "new_dialogue"), new Choice("Hidden", "hidden") },
                () => S.Str("atlas_npc_mode"), v => S.Set("atlas_npc_mode", v));
            Body.Children.Add(new TextBlock { Text = "Updates: extract the complete matching Atlas ZIP into a new folder. Your other launchers are unchanged.",
                TextWrapping = TextWrapping.Wrap, Margin = new Thickness(14, 4, 14, 12) });
'''
        s=replace(s,anchor,page+anchor)
        begin=s.index('            Group("Lantern Engine");')
        end=s.index('            Group(L.T("Performance"));',begin)
        return s[:begin]+'''            Group("Included Atlas runtime");
            Add(Card(SymbolRegular.FolderLink24, "Engine folder", "This edition uses its included Lantern-based Atlas runtime.",
                IconButton(SymbolRegular.Open24, L.T("Open in Explorer"), (_, _) => Paths.OpenFolder(Paths.PortDir)), out _portHint));

'''+s[end:]
    edit('Views/SettingsPage.cs',settings)
    edit('BloodborneLauncher.csproj',lambda s:replace(s,'<AssemblyName>Lantern Engine</AssemblyName>',
        '<AssemblyName>HuntersAtlas</AssemblyName>').replace('<Version>0.9.9</Version>','<Version>3.1.0</Version>'))
    # Use the retained Windows-port icon rather than rebranding with Lantern's logo.
    for name in ('app.ico','lantern-beta.ico','lantern-stable.ico','lantern-j3loo.ico'):
        shutil.copy2(REPO/'source/lite/integration/bloodborne.ico',app/name)
    (root/'ATLAS-LAUNCHER-INTEGRATION.json').write_text(json.dumps(proof,indent=2)+'\n')
    return app/'BloodborneLauncher.csproj'

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);a=p.parse_args()
    print(prepare(a.source.resolve()))
