# Model notes

This file records the facts that are easy to break while changing the model.
The tests are the final check.

## Signal path

Each handle owns four G, D, A, and E string states. A voice runs a two-rail
digital waveguide and returns a quiet direct signal. It also writes bridge
force into a hidden per-string lane. The force tap reads the bridge after
one-way travel from the bow. The bow reads the round-trip reflection.

The resonance opcode reads the four lanes from the prior Csound block. It
drives twelve body modes and returns wet stereo sound. A separate force
history carries string-to-string feedback across 128 samples or one engine
block, whichever is longer. Both paths work in either opcode order.

The plug-in ends at the direct and body outputs. Distance, microphone tone,
and room effects belong in the score or host.

## String state

Each string keeps:

- two travelling-wave rails and their loss filters
- pitch, stop position, and finger pressure
- bow state, contact memory, heat, and hair motion
- articulation and release state
- vibrato phase and pitch glide
- harmonic touch state
- pluck and wood-contact state
- bridge input and deterministic noise state

That state lives on the violin handle, not on one score note. A clean legato
handoff can therefore change opcode instances without restarting the string.

An exact handoff must not overlap. Direct arco keeps bow state. Tremolo also
keeps its stroke phase. A new bowed attack keeps the rails but rearms contact.
A falling trigger releases contact and starts the chosen rail damping.
An arco or détaché bow keeps its last speed and force while contact fades
with a 2 ms time constant.
Open strings played arco or détaché keep their normal rail losses and get
1 percent of the added release damping. A stopped arco or détaché string
holds its pitch when the controller or renderer asks to reopen it after
release. It reopens once its bridge RMS falls to 0.5 percent of its level at
release, or after 380 ms. A new bow stroke can change pitch at once.
Automatic reopening keeps the damping of the stopped note's tail.
On a stopped arco or détaché release, extra loss rises at lift, then eases
to let the stopped pitch ring. The normal release loss returns by 99 ms.

Short gaps step the missing samples. Medium gaps use a bounded state update.
Gaps longer than six seconds clear the rail. State must never remain frozen
through silence.

## Bow and exciters

The bow uses a main contact and a weaker second edge with a separate
stick-slip calculation and propagation delay. A small contact-memory term,
a heat state, and spring-damper hair motion add history. Force, signed speed,
and position remain live at k-rate.
Light détaché strokes build bow contact more slowly as force drops.
Arco and détaché bursts pass through a 6.5 kHz one-pole filter before they
excite the string.

The same rails also receive normal and left-hand pizzicato, Bartók pizzicato,
col legno battuto, and col legno tratto. One-shot sounds fire once per rising
edge. Their tail remains on the physical string after the edge ends.

`kStrange = 0` is the normal path. Negative values make contact weaker and
airier. Positive values add more coupling, dispersion, a bounded subharmonic,
and a high-force squeal region. Every branch has finite and level limits.

## Harmonics and pitch

The voice input always gives the sounding pitch. For harmonic order `N`, the
model derives an internal string pitch of `kFrequency / N` and places the
touch at the matching node. The touch reflects and transmits waves along the
nut-side branch. Period-based filtering helps the requested partial speak on
rapid attacks. Natural and artificial harmonics use the same stored rails.

The model increases high-frequency loss at the stopped finger. The nut-side
reflection cutoff drops as the vibrating length shortens, up to a fixed
limit. The pitch solver includes the phase of that reflection.

The optional A4 constructor value retunes all pitch-linked state together.
The score still has to send note frequencies in the same tuning.

## Body

The body is a one-way bridge-force to radiation model. It has twelve complex
modes from 265 Hz to 4.35 kHz. The 3.3 and 4.35 kHz modes use separate input
gains for each string. Fixed left and right gains give a stable stereo view.
Mode phase, smoothed gain, and decay live on the handle.

`kBody` changes wet amount, tone, and decay. `kMute` lowers and darkens the
body and raises its modal loss. The body reads no impulse response at runtime.
The string feedback uses fixed coupling gains. A measured driving-point
admittance would be needed to model bridge loading and its effect on bow force.

## Fixed data

The checked JSON under `profiles/` is build input. A Python generator validates
it and replaces the marked C table in `src/hlolli_wg_violin.c`. Never edit that
generated block by hand.

The runtime reads no JSON. It checks the embedded values once when Csound
creates the plug-in manager.

## Safety rules

- Native and WASM builds use the same canonical C file.
- One handle owns one violin. Never share it between players.
- One renderer owns one handle's body.
- All user controls are checked and clamped before they reach the model.
- All long loops have fixed bounds.
- A bad state must recover to finite bounded values.
- Test-only opcodes must stay out of the release module.
- Fitted string loss belongs inside the waveguide. Do not add output tone EQ.
- A model change needs the matching native, worker, and WASM checks.

## Sources behind the design

- Julius O. Smith, *Synthesis of Bowed Strings* (1982).
- Matthias Demoucron, *On the Control of Virtual Violins* (2008).
- Galluzzo, Woodhouse, and Mansour on friction laws for bowed strings.
- Mansour, Woodhouse, and Scavone on minimum bow force.
- Serafin, Avanzini, and Rocchesso on elasto-plastic friction.
- Maestre, Spa, and Smith on hair and thermal friction.
- Holm and Välimäki on violin body modes.
- Karjalainen on position-dependent plucks.
- Bilbao and Torin on string and fingerboard collision.

The notes under [docs/research](research/) record recent local listening and
measurement work. They are reports, not runtime inputs.

[Research sources used](research/papers-used.md) gives links and states what
each source changed or checked.
