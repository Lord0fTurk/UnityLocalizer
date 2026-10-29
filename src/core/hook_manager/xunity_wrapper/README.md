# XUnity wrapper with a delayed start

`DelayedStart.cs` is XUnity.AutoTranslator's BepInEx 5 wrapper (5.6.2) changed in one place: the translator is
started from `Update()` after three frames instead of from `Awake()`. Unity 6000.5.2 crashes when `StartCoroutine`
is called while plugins load, and XUnity's start-up calls it (see `../delayed_start.py`).

`XUnity.AutoTranslator.Plugin.BepInEx.dll` is built from that file:

```
python tools/build_xunity_wrapper.py --game-dir "<a game with BepInEx 5 + XUnity 5.6.2 installed>"
```

then copy the printed SHA256 into `WRAPPER_SHA256` in `../delayed_start.py`. The application refuses to use a DLL
whose hash differs.

## License

Derived from https://github.com/bbepis/XUnity.AutoTranslator, which is licensed under the MIT License:

Copyright (c) 2018 gravydevsupreme, Bepis and contributors

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
