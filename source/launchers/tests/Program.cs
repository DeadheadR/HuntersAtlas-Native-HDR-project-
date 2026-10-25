using BloodborneLauncher.Core;
using System.IO;
using System.Security.Cryptography;
using System.Text.Json;

if (args.Length != 1) throw new ArgumentException("Pass the verified CUSA00207 1.09 game directory.");
var root = AtlasIntegration.Root;
Directory.CreateDirectory(Path.Combine(root,"engine","out"));
File.WriteAllText(Path.Combine(root,"engine","out","bb-probe.exe"),"");
File.WriteAllText(Path.Combine(root,"engine","out","bb-start.exe"),"");
File.WriteAllText(Path.Combine(root,"package.json"),"{\"version\":\"0.9.37\",\"engine\":\"lantern-fps94-atlas-3.1\"}");
var privateProfile = Path.Combine(root,"qa-profile");
Environment.SetEnvironmentVariable("ATLAS_LAUNCHER_SETTINGS_ROOT", privateProfile);
var settings = new LauncherSettings();
settings.Set("game_dir", args[0]); settings.Set("atlas_enabled",true);
settings.Set("atlas_travel_enabled",true); settings.Set("atlas_npc_mode","hidden");
var atlas = Path.Combine(root,"atlas"); Directory.CreateDirectory(atlas);
var testFile=Path.Combine(root,"test-runtime.bin");File.WriteAllText(testFile,"known runtime");
var digest=Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(testFile))).ToLowerInvariant();
void Manifest(string target="lantern-v0.9.37", string relative="test-runtime.bin") =>
    File.WriteAllText(Path.Combine(atlas,"adapter.json"),JsonSerializer.Serialize(new {
        target, map_index_sha256=new string('a',64), launch_files=new Dictionary<string,string>{{relative,digest}}
    }));
var passed = new List<string>();
void Reject(string name, Action action) {
    try { action(); } catch(InvalidDataException) {passed.Add(name);return;}
    throw new Exception("Expected refusal: "+name);
}
Manifest();var env=new Dictionary<string,string>();AtlasIntegration.Apply(settings,env);
if(env["BB_ATLAS_ENABLED"]!="1" || env["BB_MAP_NPC_MODE"]!="hidden" || env["BB_MAP_TRAVEL_ENABLED"]!="1")throw new Exception("Wrong settings");
passed.Add("supported game and Atlas settings");
if(Paths.ConfigDir!=privateProfile || !File.Exists(Path.Combine(privateProfile,"settings.json")))throw new Exception("Profile isolation failed");
passed.Add("private profile");
Paths.PortDir="C:\\wrong-engine";
if(Paths.PortDir!=root || GameRunner.Custom(settings) || !AtlasIntegration.ProtectRuntimeUpdates)throw new Exception("Runtime escape");
passed.Add("fixed engine and protected updates");
if(Updater.OwnPackage==null || Updater.EngineOutdated)throw new Exception("Matching Atlas engine incorrectly asks for an update");
if(Updater.LatestAsync().GetAwaiter().GetResult()!=null)throw new Exception("Stock updates still offered");
passed.Add("matching engine launches without stock update prompt");
settings.Set("atlas_enabled",false);AtlasIntegration.Apply(settings,env);
if(env["BB_ATLAS_ENABLED"]!="0" || env["BB_MAP_TRAVEL_ENABLED"]!="0")throw new Exception("Disabled Atlas still travels");
passed.Add("disabled Atlas disables travel");
Manifest("different-engine");Reject("mixed engine rejected",()=>AtlasIntegration.Apply(settings,env));
Manifest();File.AppendAllText(testFile,"tamper");Reject("changed runtime rejected",()=>AtlasIntegration.Apply(settings,env));
Manifest(relative:"../outside.bin");Reject("path traversal rejected",()=>AtlasIntegration.Apply(settings,env));
Manifest();settings.Set("game_dir",root);Reject("unknown game rejected",()=>AtlasIntegration.Apply(settings,env));
Console.WriteLine(JsonSerializer.Serialize(new{pass_all=true,tests=passed},new JsonSerializerOptions{WriteIndented=true}));
