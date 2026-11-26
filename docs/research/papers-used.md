# Research sources used

This list covers work that changed the model, its fixed data, a score control,
a test, or a design choice. It includes one thesis because it had a direct role.
It does not list papers that we only read and did not use.

The labels show how each source affected the project:

- **Direct:** a model part or fixed value came from the source.
- **Adapted:** the source gave us the idea, but this code uses a smaller form.
- **Control/test:** the source set a score rule or a test target.
- **Diagnosis:** the source helped explain a fault or plan a later change. It
  did not change the shipped model.

## String, bow, body, and contact

- **Direct — Julius O. Smith III, “Synthesis of Bowed Strings” (ICMC 1982).**
  [ICMC archive record](https://hdl.handle.net/2027/spo.bbp2372.1982.028),
  [DBLP record](https://dblp.org/rec/conf/icmc/Smith82).
  This gave us the two travelling-wave rails, the bow junction, loop loss, and
  a separate body response. It is the base of the string model.

- **Control/test — Matthias Demoucron, “On the Control of Virtual Violins:
  Physical Modelling and Control of Bowed String Instruments” (doctoral
  thesis, 2008).**
  [KTH record and full text](https://kth.diva-portal.org/smash/record.jsf?pid=diva2%3A113911).
  It maps bow force, bow speed, and distance from bow to bridge to stable tone,
  level, and tone colour. Its measured detache, martele, spiccato, tremolo, and
  bow-change shapes guided the small set of bow controls and gesture tests.

- **Adapted — P. M. Galluzzo, Jim Woodhouse, and H. Mansour, “Assessing
  Friction Laws for Simulating Bowed-String Motion” (2017).**
  [Cambridge record and accepted paper](https://www.repository.cam.ac.uk/items/872131e9-6e51-4d90-a5ee-dde02409ebe3),
  [DOI](https://doi.org/10.3813/AAA.919136).
  Their machine-bow tests found that contact-temperature friction matched
  transients better than laws based only on current sliding speed. This backed
  our use of contact history and our attack and bow-force tests.

- **Adapted — H. Mansour, Jim Woodhouse, and Gary P. Scavone, “On Minimum
  Bow Force for Bowed Strings” (2017).**
  [Cambridge record and accepted paper](https://www.repository.cam.ac.uk/items/d95ed38b-bb3e-4064-bd80-ec7f455d70d0),
  [DOI](https://doi.org/10.3813/AAA.919060).
  It shows that the least force needed for stable Helmholtz motion depends on
  bow position and body motion. This guided the bow-position force bounds and
  the tests for stable tone across the normal contact range.

- **Adapted — Stefania Serafin, Federico Avanzini, and Davide Rocchesso,
  “Bowed String Simulation Using an Elasto-Plastic Friction Model” (SMAC
  2003).**
  [Author PDF](https://avanzini.di.unimi.it/downloads/publications/serafin_smac03.pdf),
  [University of Padua record](https://research.unipd.it/handle/11577/1374020).
  It adds pre-slip motion and friction memory instead of using a memoryless
  curve. Our short contact-memory state is a cheap, bounded form of that idea;
  it is not the full method from the paper.

- **Adapted — Esteban Maestre, Carlos Spa, and Julius O. Smith III, “A Bowed
  String Physical Model Including Finite-Width Thermal Friction and Hair
  Dynamics” (ICMC/SMC 2014).**
  [Zenodo record and paper](https://zenodo.org/records/850848),
  [DOI](https://doi.org/10.5281/zenodo.850848).
  This joined heat-based rosin friction with moving bow hair. It led to the
  small heat state and spring-damper hair state in the plug-in. We did not copy
  its full finite-width or two-polarisation model.

- **Direct — J.-M. Holm and Vesa Valimaki, “Modeling and Modification of
  Violin Body Modes for Sound Synthesis” (EUSIPCO 2000).**
  [Aalto record](https://research.aalto.fi/en/publications/modeling-and-modification-of-violin-body-modes-for-sound-synthesi/),
  [paper PDF](https://eurasip.org/Proceedings/Eusipco/Eusipco2000/SESSIONS/FRIPM/SS1/CR1706.PDF).
  Table 1 supplied the frequency, width, and relative level of the five low
  body modes in `profiles/measurements/holm_valimaki_2000_table1.json`. The
  other seven modes came from later project fits.

- **Adapted — Matti Karjalainen, Vesa Valimaki, and Tero Tolonen,
  “Plucked-String Models: From the Karplus-Strong Algorithm to Digital
  Waveguides and Beyond” (1998).**
  [Aalto record](https://research.aalto.fi/en/publications/plucked-string-models-from-the-karplus-strong-algorithm-to-digita/),
  [DOI](https://doi.org/10.2307/3681155).
  It explains how the pluck point changes the partial pattern in a waveguide.
  This guided point-based pizzicato input and the test that moving the pluck
  point changes the sound.

- **Adapted — Stefan Bilbao and Alberto Torin, “Numerical Modeling and Sound
  Synthesis for Articulated String/Fretboard Interactions” (2015).**
  [Edinburgh record](https://www.research.ed.ac.uk/en/publications/numerical-modeling-and-sound-synthesis-for-articulated-stringfret),
  [DOI](https://doi.org/10.17743/jaes.2015.0023).
  It gave a power-law contact force and an energy-safe way to handle string and
  board contact. We used that as a guide for bounded fingerboard and wood-hit
  contact. We did not copy its full guitar FDTD model.

## Vibrato controls and tests

- **Control/test — Maureen Mellody and Gregory Wakefield, “The Time-Frequency
  Characteristics of Violin Vibrato” (2000).**
  [DOI](https://doi.org/10.1121/1.428326),
  [PubMed record](https://pubmed.ncbi.nlm.nih.gov/10641668/).
  Ten tones gave a mean rate of 5.9 Hz and a mean pitch depth of 15.2 cents.
  The paper also found level change in each partial. This set the centre of our
  normal range and warned us not to add one gain LFO to the whole sound.

- **Control/test — Erwin Schoonderwaldt and Anders Friberg, “Toward a
  Rule-Based Model for Violin Vibrato” (2001).**
  [Author-uploaded paper](https://www.researchgate.net/publication/254472747_TOWARD_A_RULE-BASED_MODEL_FOR_VIOLIN_VIBRATO),
  [KTH project report](https://www.speech.kth.se/music/publications/rapport/2001/musFrame-1.htm).
  It supplied the first note-shape targets: little vibrato below 350 ms, a late
  start on long notes, a shaped rise and fall, depth tied in part to level, and
  a small rate rise near some endings.

- **Control/test — Julieta Gleiser, Anders Friberg, and Svante Granqvist, “A
  Method for Extracting Vibrato Parameters Applied to Violin Performance”
  (1998).**
  [Author-uploaded paper](https://www.researchgate.net/publication/265010728_A_method_for_extracting_vibrato_parameters_applied_to_violin_performance),
  [KTH author record](https://www.kth.se/profile/ssg/publications).
  It tracks pitch, rate, depth, and level through each note. Its examples show
  that rate and depth move within a note, depth often follows level, and some
  notes begin vibrato after the level peak. This guided separate slow drift in
  rate and depth.

- **Control/test — Luwei Yang, Elaine Chew, and Khalid Rajab, “Vibrato
  Performance Style: A Case Study Comparing Erhu and Violin” (2013).**
  [Author PDF](https://luweiyang.com/wp-content/uploads/2016/05/cmmr2013_luwei_yang.pdf).
  Its violin notes ranged from 5.13 to 8.23 Hz and 4 to 32 cents of depth. The
  measured pitch shapes only partly matched a sine, and long notes could have
  more than one depth rise. This backed a near-sine carrier with slow spline
  drift instead of one fixed, perfect sine.

- **Control/test — Rebecca B. MacLeod, “Influences of Dynamic Level and Pitch
  Register on the Vibrato Rates and Widths of Violin and Viola Players”
  (2008).**
  [DOI](https://doi.org/10.1177/0022429408323070),
  [University of Illinois record](https://experts.illinois.edu/en/publications/influences-of-dynamic-level-and-pitch-register-on-the-vibrato-rat/).
  Higher notes were about 0.32 Hz faster and 26 cents wider in total; loud
  notes were about 4 cents wider. This guided the small pitch and level changes
  in the Chaconne vibrato controls.

- **Control/test — Rebecca B. MacLeod, “A Pilot Study of Relationships
  between Pitch Register and Dynamic Level and Vibrato Rate and Width in
  Professional Violinists” (2010).**
  [DOI](https://doi.org/10.1177/194849921000100105).
  Four soloists had a mean rate of 6.63 Hz and a mean total width of 63 cents.
  This gave us a modern solo range, not one fixed setting for Bach.

- **Control/test — Michael L. Allen, John M. Geringer, and Rebecca B.
  MacLeod, “Performance Practice of Violin Vibrato: An Artist-Level Case
  Study” (2009).**
  [DOI](https://doi.org/10.1177/1948499209OS-400103).
  One player used about 5.7 Hz in first position and 6.3 Hz in fifth, moved
  above and below the pitch centre, began downward, and paused at slurred note
  changes. We used it as a choice for transitions, not a rule for all players.

- **Control/test — John M. Geringer, Michael L. Allen, and Rebecca B.
  MacLeod, “Initial Movement and Continuity in Vibrato among High School and
  University String Players” (2005).**
  [DOI](https://doi.org/10.1177/002242940505300306).
  All 40 players paused vibrato at the tested slurred changes. Mean gaps were
  0.42 s for university players and 0.50 s for school players. This backed a
  short break at a finger change, while the artist study gave the better target
  for the solo demo.

## Used in the open-string spectrum diagnosis

- **Diagnosis — Erwin Schoonderwaldt, Knut Guettler, and Anders Askenfelt,
  “Effect of the Width of the Bow Hair on the Violin String Spectrum” (SMAC
  2003).**
  [Author PDF](https://knutsacoustics.com/files/bow-width-smac03-.pdf).
  Narrowing the hair raised high partials by about 2 to 4 dB per tested width
  step above partial 11, with single changes up to 6 dB. This helped explain
  why a point bow may sound too bright. It also stopped us from treating string
  loss as a plain output tone control.

- **Diagnosis — Stefania Serafin and Julius O. Smith III, “A Multirate,
  Finite-Width, Bow-String Interaction Model” (DAFx 2000).**
  [DAFx paper PDF](https://www.dafx.de/paper-archive/2000/pdf/Serafin_Stefania_paper.pdf).
  It gives an efficient way to model two bow edges and the short delay between
  them. It guided the model's second bow contact and its short propagation delay.

## Not in this list

Leopold Mozart's 1756 violin method is a useful first-hand source for style,
but it is not a research paper. Csound manuals and source code explain the
opcodes we used, but they are software sources. Private recordings and local
reports supplied fit clips and pass limits, but they are project data.
