# Opcode API

The plug-in has three public opcode names. Create one handle, run one voice for
each active string, and run one resonance opcode for the body.

## Create a violin

```csound
giViolin hlolli_wg_violin_create
giViolin442 hlolli_wg_violin_create 442
```

The optional i-rate number is the A4 reference pitch in hertz. It accepts 380
through 480 and defaults to 440. It retunes the open strings, stopped-string
geometry, harmonics, automatic string choice, and sympathetic response.

Create handles in the global orchestra header. One handle means one violin and
one player. Handles live until Csound resets.

The old string forms still accept the exact built-in model name for old scores.
New code should use the two forms above.

## Play a string

```csound
aLeft, aRight hlolli_wg_violin \
    kTrigger, kFrequency, kForce, kSpeed, kPosition, \
    kVibratoDepth, kVibratoRate, kArticulation, \
    kHarmonic, kStrange, iString, giViolin
```

The signature is `aa <- kkkkkkkkkkii`.

| Input | Range | Meaning |
|---|---:|---|
| `kTrigger` | 0 to 1 | Positive holds contact. A rising edge starts an attack. Zero releases it. |
| `kFrequency` | 20 to 5000 Hz | Sounding pitch. |
| `kForce` | 0 to 1 | Bow force, pluck pull, or stick force. |
| `kSpeed` | -1 to 1 | Signed bow, pluck, or stick speed. |
| `kPosition` | 0.01 to 0.49 | Contact point as a fraction of string length from the bridge. |
| `kVibratoDepth` | 0 to 200 cents | Pitch depth. |
| `kVibratoRate` | 0 to 20 Hz | Vibrato rate. |
| `kArticulation` | 0 to 15 | Articulation code below. |
| `kHarmonic` | 0 or 2 to 8 | Normal stopping or harmonic order. |
| `kStrange` | -1 to 1 | Bow-contact range. Zero is the neutral violin. |
| `iString` | 0 to 4 | Auto, G, D, A, or E. Fixed for this opcode instance. |
| `giViolin` | handle | The value returned by the create opcode. |

These narrower ranges have worked well in the supplied scores:

| Control | Musical range |
|---|---:|
| `kForce` | 0.22 to 0.73 |
| `kSpeed` | -0.72 to 0.72 |
| `kPosition` | 0.12 to 0.28 |
| `kVibratoDepth` | 0 to 22 cents |
| `kVibratoRate` | 4.9 to 5.7 Hz |
| `kStrange` | 0 |

## Articulations

| Code | Sound |
|---:|---|
| 0 | Direct arco and legato |
| 1 | Détaché |
| 2 | Martelé |
| 3 | Spiccato |
| 4 | Tremolo |
| 5 | Pizzicato. Speed sign selects right or left hand. |
| 6 | Bartók pizzicato |
| 7 | Col legno battuto |
| 8 | Col legno tratto |
| 9 to 15 | Reserved and silent |

Keep `kTrigger` positive across a direct same-string slur. A falling edge adds
the release damping for the active articulation. Codes 5 through 7 fire once
on a rising edge. Tremolo and col legno tratto run while the gate stays high.

`kHarmonic` keeps `kFrequency` as the pitch you want to hear. The model derives
the lower string pitch and touch point. An unsafe harmonic falls back to normal
stopping without clearing the string.

Automatic string choice rejects notes below open G. It uses the highest string
that can play the pitch, unless an exact same-sample legato handoff can keep the
current string.

## Render the body

```csound
aLeft, aRight hlolli_wg_violin_resonance \
    giViolin, kBody, kSympathetic, kMute
```

The signature is `aa <- ikkk`.

| Input | Range | Meaning |
|---|---:|---|
| `kBody` | 0 to 1 | Body level, tone, and decay. Zero mutes this output. |
| `kSympathetic` | 0 to 1 | Bridge drive into open strings. Zero is exact off. |
| `kMute` | 0 to 1 | Darkens and shortens the body as a practice mute would. |

One resonance opcode owns the body for one handle. It reads bridge force from
the prior Csound block, so its wet output arrives one `ksmps` block after the
direct strings. Keep it running for as long as you need the body tail.

## State rules

- One voice instance owns one physical string at a time.
- Use separate voice instances on separate strings for double stops.
- A release changes contact and damping. It does not erase the string.
- Exact handoffs keep the string rails and the state that should carry on.
- Long silent gaps decay or clear old state instead of freezing it.
- Separate handles never share string, body, phase, or random state.
- Use `--sample-accurate --num-threads=1` for exact offline comparisons.
