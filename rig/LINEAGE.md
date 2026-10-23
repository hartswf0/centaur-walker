# Centaur Rig: lineage

This is a second line of the centaur work, separate from the Walker and build-book line in the repo root. Its legs are cut from 1 in EPS foam or 1/4 in plywood, and they run on the original Jansen lengths. The line ends in two builds:

- **Backpack:** the legs hang from your hip belt and are driven by a ground wheel.
- **Bike:** the legs hang from the rear rack and are driven by a roller on the rear tyre.

Each entry below gives the file, the request that led to it, and what changed. All pages are single HTML files.

## Versions

| # | File | Request | What changed |
|---|---|---|---|
| 21 | [versions/21-stride-plate.html](../versions/21-stride-plate.html) | Redesign the GeoGebra Jansen horse with six principles: show the hidden state, get past the limits of memory, several views, direct manipulation, semantic zoom, constrained play. | **Stride Plate.** A Muybridge-style plate of the stride, the linkage with draggable bars, and the foot path. |
| 22 | [versions/22-centaur-rig-v1.html](../versions/22-centaur-rig-v1.html) | See each joint in time. Make every joint a hole in a flat plate, like a brad puppet. Human front legs, Jansen hind legs, power from walking or a bike crank. | **Joint timeline:** load, swing and knock per pin. **Pins as holes in plates.** **Three drives:** ground wheel, hand crank, thigh rods. **Layer order** worked out from the parts and the pins that pass through them. |
| 23 | [versions/23-centaur-rig-v2.html](../versions/23-centaur-rig-v2.html) | One pair of legs only, hung off a backpack or sitting on the bike's rear rack, driven by a friction roller on the back tyre. Easier to build and understand. | **One pair of legs.** **Bike geometry:** rack, roller on the tyre, reduction box, rider. **Per-layer panels** and a build list. |
| 24 | [versions/24-centaur-rig-v3.html](../versions/24-centaur-rig-v3.html) | A no-scroll physics bench, not a textbook. Legs must touch the ground in the same plane as the human legs. Model how it breaks, slop and loose tolerance. | **One-screen bench.** **Two checks:** feet on the ground, in your foot plane. **Failure models:** EPS crush, buckling and wear. **Slop:** a cloud of where the foot can wander. |
| 25 | [versions/25-centaur-rig-v4.html](../versions/25-centaur-rig-v4.html) | Layers, thickness, friction, sound. Options swappable like a game builder, without covering the sim. Tolerances. How to actually build it. | **Layer stack** with real thicknesses. **Pin friction** with sound. **Variants A–D** with copy-to-next. **Making tolerances:** hand, jig, CNC. **Workshop tab.** |
| 26 | [versions/26-centaur-rig-v5.html](../versions/26-centaur-rig-v5.html) | "Way worse." Always keep the sim and the part visible on a phone; half the screen can be controls. The joints are the hardest part. | **Phone-first layout:** sim and part on top, controls below. **Nine joint types** compared at every pin: brad, rivet, scissor pivot, puck, pipe in tee, bush, clevis, webbing, 608 bearing. |
| — | [rig/centaur-rig.html](centaur-rig.html) | Bring the bicycle, the centaur and Muybridge back into one final engine. Real materials and dimensions, so someone can build it and think through every detail, with less text. Reference: the Centaur of Volos. | **Walk and Bike modes** on one engine. **Muybridge 16-frame plate.** **Real stock and joints** with prices. **Dimensioned part drawings**, pin stacks with bolt lengths, cut list and buy list. Presets were later updated to match the design set. |
| 27 | [versions/27-build-shop-prompt.html](../versions/27-build-shop-prompt.html) | Give the centaur rig prompt in the form of SCION (autonomous studio, independent critique, recursive inquiry), in operational language. | **15 sections** tied to the leg. **Test piece:** the knee (J2) under load for 100 turns. **References:** Muybridge and Volos. **Checkers** who did not build the part. |
| — | [rig/design-set.html](design-set.html) + [files/](files/) | Run the swarm and make the fully integrated final design files: one on a backpack, one on the back of a bike, all of the work. | **Design set:** 20 sheets for Backpack, 18 for Bike. **Files:** 1:1 SVG and DXF for every part, tiled Letter PDFs, design-data.json. |

## How the design set was made

**1. Inquiry: can the linkage keep a foot down longer?**
- **Question:** a horse walk keeps each foot down about 60% of the stride; the Jansen lengths give 43%. Can new lengths do better?
- **Test:** a search over the link lengths (`source/duty.js`), counting a foot as down when it is within 10 mm of its lowest point and requiring little slide.
- **Result:** the best was 47%.
- **Decision:** keep the original lengths and record the 44% as a known limit.

**2. Choosing materials and joints.** The engine ran every material against four joint policies for both modes (`source/grid.js`). The chosen builds:

| | Backpack | Bike |
|---|---|---|
| Material | 1 in EPS, dowel spine in the long links | 1/4 in plywood |
| Joints | 1/4 in ply cheek discs, flanged nylon bushes on M8 bolts | flanged nylon bushes; 608 bearings at the crank axle |
| Frame and crank | doubled plywood | doubled plywood |

**3. Drive geometry.**
- **Direction:** seen from the rig's right side while it moves to the right, the crank must turn clockwise, the same way as the wheels.
- **Gears:** a friction roller reverses direction, so each drive has one spur pair to reverse it back.
- **Backpack:** 7.5:1, giving 1296 mm of ground per crank turn, the same as the stride.
- **Bike:** 1:27, giving 60 rpm at 16 km/h.

**4. Independent review in four rounds.** Each round used checker agents that had not built the files. They recomputed the files, swept every part through a full crank turn and rendered every sheet.

| Round | Found | Fixed by |
|---|---|---|
| 1 | Crank-rod hardware swept through the j and k links. The bike crank-pin head swept through the frame. The rotation-test wording was mirrored. No belt tension. Rack brackets did not reach the frames. The roller spun free of its shaft. | **Captive nuts** in the cranks with the rod ending flush. **Wider layer gap** on the bike. **Shaft table** with z positions. **Mounts sheet.** **Epoxy-putty** roller lock. |
| 2 | The saddle block hit the spur. The bike roller shaft was too short. The hex recess was deeper than one ply layer. There were no anchors or tension method, and the belt clamp could not pass the 16T pulley. | **Saddle block** centred. **Shafts** recut. **Thin nuts** in the recess. **Roll pin.** **Mount drawings.** **Tiled PDFs.** |
| 3 | The bike spring lifted the roller. The backpack bungee lifted the wheel. The idler could not take up the slack. The box clipped the rack angle. | **Sprung toothed idler** on a lever. **1 kg steel bar** on the arm. **Spring tail** behind the hinge. **Box** moved inward. **Board** widened to 320. |
| 4 | Angle holes crossed. Labels were clipped. | **Hole positions** moved; **title text** wrapped. The spring fix was checked by calculation: about 11 N on the tyre. |

**What the final review confirmed.** Every hole spacing matches the linkage × scale to 0.01 mm. Every bolt meets grip + nut + 2.5 mm. No part collides over a full turn.

## Known limits (computed, not yet built)

- Each hind foot is down 44% of a crank turn; a horse walk is about 60%.
- **Backpack:** the ground wheel keeps the rig in step by distance, not by your steps, so the feet drift in and out of phase over about 30 strides. The wheel shows under the body unless the rump covering hides it.
- **Bike:** the legs never touch the road. The rack struts are assumed to be 67 mm from the tyre centre; measure yours.
- Nothing here has been built or measured yet. The first test is the Backpack knee (J2) from the Pin stacks sheet: load it as given on the Checks sheet and turn it 100 times.

## Key numbers

| | Backpack | Bike |
|---|---|---|
| Crank axle | 899 mm | 700 mm |
| One crank turn | 1296 mm of ground | 4411 mm of road |
| Crank speed | 54 rpm (your walk) | 60 rpm at 16 km/h |
| Weight | 3.9 kg | 3.2 kg |
| Parts, rough US | about $234 | about $190 |
