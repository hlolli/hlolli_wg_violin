# Paganini Caprice No. 24

This score plays the theme, eleven variations, and finale. It expands written
repeats and keeps dynamics, accents, dots, chords, trills, slurs, and the 75
left-hand pizzicato notes in Variation IX.

The plug-in handles every note with four persistent string controllers and one
body. Same-string slurs keep the bow gate high. Separate bowed notes use
détaché, martelé, or spiccato from the score mark. The score adds no bow
tremolo because Paganini wrote none.

## Play

```sh
cmake --build build --target play_paganini_caprice_24
```

The target opens the default audio device. A direct macOS command is:

```sh
csound -odac \
  --opcode-lib=build/libhlolli_wg_violin.dylib \
  --sample-accurate --num-threads=1 \
  examples/paganini_caprice_24.csd
```

Use `.so` on Linux or `.dll` on Windows.

The default mix has a quiet guide synth. Hear only the violin with:

```sh
csound -odac \
  --omacro:GUIDE_LEVEL=0 \
  --opcode-lib=build/libhlolli_wg_violin.dylib \
  --sample-accurate --num-threads=1 \
  examples/paganini_caprice_24.csd
```

Useful macros:

| Macro | Use |
|---|---|
| `GUIDE_LEVEL=0` | Turn off the guide synth |
| `DIRECT_LEVEL=0` | Hear the body alone |
| `BODY_LEVEL=0` | Hear direct strings alone |
| `SYMPATHETIC_LEVEL=0` | Turn open-string bridge drive off |
| `SHOW_MARKS=0` | Hide printed section names |
| `PRACTICE_HARMONICS=1` | Add an optional Variation X harmonic exercise |

The practice harmonic is not in the printed score. It is off by default.

## Church render

The separate convolution score uses a local St Nicolaes Church impulse. The
impulse is not part of this repo.

```sh
cmake --build build --target render_paganini_caprice_24_ftconv
```

The target writes `build/paganini_caprice_24_ftconv.wav`. It looks for:

```text
$HOME/Downloads/IMReverbs/St Nicolaes Church.wav
```

Set another file at configure time:

```sh
cmake -S . -B build \
  -DHLOLLI_ST_NICOLAES_IR=/absolute/path/room.wav
cmake --build build --target render_paganini_caprice_24_ftconv
```

The CSD uses `GEN52` to copy the stereo impulse into the channel order needed
by `ftconv`. It keeps the dry violin outside the convolution path.
