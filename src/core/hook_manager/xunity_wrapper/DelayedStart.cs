// UnityLocalizer: XUnity.AutoTranslator BepInEx 5 wrapper that starts the translator a few frames late.
//
// Derived from XUnity.AutoTranslator.Plugin.BepInEx 5.6.2 (https://github.com/bbepis/XUnity.AutoTranslator),
// Copyright (c) 2018 gravydevsupreme, Bepis and contributors, MIT License (see README.md in this folder).
//
// Why: on Unity 6000.5 calling StartCoroutine while the plugins are being loaded (before the player loop runs)
// kills the player with an access violation inside UnityPlayer.dll, and XUnity's start-up starts a coroutine.
// The original wrapper calls PluginLoader.LoadWithConfig from Awake; this one calls it from Update() once a few
// frames have passed. The plugin GUID, name and version are unchanged, so the config and dependants keep working.
//
// Build: see README.md (tools/build_xunity_wrapper.py).
using System.IO;
using System.Reflection;
using BepInEx;
using ExIni;
using XUnity.AutoTranslator.Plugin.Core;

[assembly: AssemblyTitle("XUnity.AutoTranslator.Plugin.BepInEx")]
[assembly: AssemblyProduct("XUnity.AutoTranslator.Plugin.BepInEx (UnityLocalizer delayed start)")]
[assembly: AssemblyVersion("5.6.2.0")]
[assembly: AssemblyFileVersion("5.6.2.0")]

namespace XUnity.AutoTranslator.Plugin.BepInEx
{
    /// <summary>Where XUnity reads its configuration from and keeps translations; same values as the original wrapper.</summary>
    internal class Environment : IPluginEnvironment
    {
        private IniFile _file;
        private readonly string _configPath;

        public Environment()
        {
            ConfigPath = Paths.ConfigPath;
            TranslationPath = Paths.BepInExRootPath;
            _configPath = Path.Combine(ConfigPath, "AutoTranslatorConfig.ini");
        }

        public IniFile Preferences
        {
            get { return _file ?? (_file = Load()); }
        }

        public string ConfigPath { get; private set; }

        public string TranslationPath { get; private set; }

        public bool AllowDefaultInitializeHarmonyDetourBridge
        {
            get { return false; }
        }

        private IniFile Load()
        {
            return File.Exists(_configPath) ? IniFile.FromFile(_configPath) : new IniFile();
        }

        public void SaveConfig()
        {
            _file.Save(_configPath);
        }
    }

    [BepInPlugin("gravydevsupreme.xunity.autotranslator", "XUnity Auto Translator", "5.6.2")]
    public class AutoTranslatorPlugin : BaseUnityPlugin
    {
        private const int FramesBeforeStart = 3;

        private int _frames;
        private bool _started;

        private void Awake()
        {
            Logger.LogInfo("XUnity Auto Translator will start after the first frames (Unity 6000.5 workaround)");
        }

        private void Update()
        {
            if (_started || ++_frames < FramesBeforeStart)
            {
                return;
            }

            _started = true;
            PluginLoader.LoadWithConfig(new Environment());
            enabled = false;
        }
    }
}
