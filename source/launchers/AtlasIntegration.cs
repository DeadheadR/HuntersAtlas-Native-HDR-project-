// SPDX-License-Identifier: GPL-3.0-or-later
// Hunter's Atlas integration for a modified build based on Lantern Engine v0.9.37.
using System.IO;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace BloodborneLauncher.Core;

public static class AtlasIntegration
{
    public const string Product = "Hunter's Atlas 3.1";
    public const string Credit = "Lantern Engine by Awaken (https://github.com/Awakenchan/LanternEngine)";
    public const string Modified = "Modified for Hunter's Atlas; this is not an official Lantern Engine release.";
    public static bool ProtectRuntimeUpdates => true;
    public static bool AllowLegacyRename => false;
    public static string Root => AppContext.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar);
    public static void Trace(string stage)
    {
        if (Environment.GetEnvironmentVariable("ATLAS_LAUNCH_TRACE") is not { Length: > 0 } path) return;
        try { File.AppendAllText(path, DateTime.UtcNow.ToString("O") + " " + stage + "\n"); } catch (IOException) { }
    }

    // This edition never writes the settings of either existing launcher.
    public static string ConfigDirectory()
    {
        var folder = Environment.GetEnvironmentVariable("ATLAS_LAUNCHER_SETTINGS_ROOT") is { Length: > 0 } custom
            ? Path.GetFullPath(custom) : Path.Combine(Root, "state", "profile");
        Directory.CreateDirectory(folder);
        var file = Path.Combine(folder, "settings.json");
        if (!File.Exists(file))
        {
            var seed = new JsonObject();
            foreach (var name in new[] { "Lantern Engine", "bbport-launcher" })
            {
                var origin = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), name, "settings.json");
                try
                {
                    if (!File.Exists(origin) || JsonNode.Parse(File.ReadAllText(origin)) is not JsonObject source) continue;
                    // Import paths and ordinary preferences only. Accounts and secrets stay with their launcher.
                    foreach (var key in new[] { "game_dir", "user_dir", "dlc_dir", "language", "voice_language", "ui_language", "fullscreen", "present_mode", "fps_mode" })
                        if (source[key] is { } value) seed[key] = value.DeepClone();
                    if (seed["game_dir"]?.GetValue<string>() is { Length: > 0 } game && File.Exists(Path.Combine(game, "eboot.bin"))) break;
                }
                catch (Exception e) when (e is IOException or JsonException or InvalidOperationException) { }
            }
            seed["check_updates"] = false;
            seed["atlas_enabled"] = true;
            seed["atlas_travel_enabled"] = true;
            seed["atlas_npc_mode"] = "all";
            seed["atlas_items_enabled"] = false;
            seed["atlas_fog_enabled"] = false;
            seed["save_backups"] = true;
            seed["discord_status"] = "off";
            File.WriteAllText(file, seed.ToJsonString(new JsonSerializerOptions { WriteIndented = true }));
        }
        return folder;
    }

    private static string CheckedPath(string root, string relative)
    {
        if (Path.IsPathRooted(relative) || relative.Contains(':') || relative.Split('/', '\\').Any(p => p is "" or "." or ".."))
            throw new InvalidDataException("Invalid Atlas package path.");
        var path = Path.GetFullPath(Path.Combine(root, relative));
        if (!path.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("Atlas package path is outside the installed folder.");
        return path;
    }

    public static void Apply(LauncherSettings settings, Dictionary<string, string> env)
    {
        Trace("Atlas: checking game and runtime");
        var game = GameCheck.Inspect(GameEnvironment.GameDir(settings));
        if (game.TitleId != "CUSA00207" || game.Version != "01.09")
            throw new InvalidDataException("This Atlas adapter supports CUSA00207 update 1.09. Select that game folder before playing.");
        var executable = Path.Combine(GameCheck.UpdateFolder(GameEnvironment.GameDir(settings)) ?? GameEnvironment.GameDir(settings), "eboot.bin");
        using (var input = File.OpenRead(executable))
            if (Convert.ToHexString(SHA256.HashData(input)).ToLowerInvariant() != "d65f0b4f01d59166aed16f8604196d8b7dd805abbf0758b356e8f1354c9429f9")
                throw new InvalidDataException("The selected game executable does not match the supported Atlas 1.09 layout.");
        var atlas = Path.Combine(Root, "atlas");
        using var manifest = JsonDocument.Parse(File.ReadAllText(Path.Combine(atlas, "adapter.json")));
        var proof = manifest.RootElement;
        if (proof.GetProperty("target").GetString() != "lantern-v0.9.37")
            throw new InvalidDataException("This Atlas package targets a different engine. Extract the complete matching ZIP.");
        foreach (var file in proof.GetProperty("launch_files").EnumerateObject())
        {
            var path = CheckedPath(Root, file.Name);
            using var stream = File.OpenRead(path);
            var actual = Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
            if (!string.Equals(actual, file.Value.GetString(), StringComparison.Ordinal))
                throw new InvalidDataException("Atlas runtime file changed: " + file.Name + ". Extract the complete matching Atlas ZIP into a new folder.");
        }
        env["BB_ATLAS_ENABLED"] = settings.Bool("atlas_enabled") ? "1" : "0";
        env["BB_ATLAS2_ENABLED"] = "1";
        env["BB_ATLAS2_DIR"] = Path.Combine(atlas, "maps-baked");
        env["BB_ATLAS2_INDEX_SHA256"] = proof.GetProperty("map_index_sha256").GetString()!;
        env["BB_ATLAS2_ASYNC_LOAD"] = "1";
        // Retain Atlas's conservative draw-preparation policy for this adapter.
        env["BB_PREP_WORKERS"] = "0";
        env["BB_MAP_DIR"] = Path.Combine(atlas, "reference", "maps");
        env["BB_MAP_CATALOG"] = Path.Combine(atlas, "reference", "maps", "catalog.json");
        env["BB_MAP_ART_DIR"] = Path.Combine(atlas, "reference", "art");
        env["BB_MAP_FONT"] = Path.Combine(atlas, "reference", "art", "native-font.ttf");
        env["BB_MAP_CONFIG"] = Path.Combine(Paths.ConfigDir, "map-settings.ini");
        env["BB_MAP_NPC_MODE"] = settings.Str("atlas_npc_mode") is "all" or "new_dialogue" or "hidden" ? settings.Str("atlas_npc_mode") : "all";
        env["BB_MAP_ITEMS_ENABLED"] = settings.Bool("atlas_items_enabled") ? "1" : "0";
        env["BB_MAP_ITEM_CATEGORIES"] = "healing,insight,equipment,echoes";
        env["BB_MAP_TRAVEL_ENABLED"] = settings.Bool("atlas_enabled") && settings.Bool("atlas_travel_enabled") ? "1" : "0";
        env["BB_MAP_FOG_ENABLED"] = settings.Bool("atlas_fog_enabled") ? "1" : "0";
        env.Remove("BB_ATLAS2_REFERENCE_DIR");
        env.Remove("BB_ATLAS2_MEASURE");
        Trace("Atlas: launch environment ready");
    }
}
