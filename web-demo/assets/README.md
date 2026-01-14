# Avatar Assets

This directory is reserved for static avatar assets if you want to use sprite-based animation instead of programmatic canvas rendering.

## Current Implementation

The demo currently uses **programmatic canvas rendering** instead of sprites. This approach:
- Eliminates the need for external sprite assets
- Provides smooth interpolation between mouth shapes
- Allows dynamic customization of avatar appearance
- Reduces initial load time

## If You Want Sprite-Based Animation

If you prefer to use sprite sheets, you can add them here:

### Mouth Sprites
Create a sprite sheet with the following viseme frames:
- `REST` - Neutral/closed mouth
- `AA` - Open mouth (ah, uh sounds)
- `EE` - Wide mouth (ee, eh sounds)
- `OH` - Rounded open mouth (oh, ow sounds)
- `OO` - Tight rounded mouth (oo, w sounds)
- `FF` - Upper teeth on lower lip (f, v sounds)
- `TH` - Tongue visible (th, l sounds)

Recommended size: 256x256 pixels per frame

### Eye Sprites
Create frames for:
- `open` - Normal open eyes
- `half` - Half-closed eyes
- `closed` - Fully closed eyes (blink)
- `left`, `right`, `up`, `down` - Saccade positions

### File Naming Convention
```
mouth_REST.png
mouth_AA.png
mouth_EE.png
...
eye_open.png
eye_closed.png
...
```

### Or Use Sprite Sheets
```
mouth_spritesheet.png  (horizontal strip)
eye_spritesheet.png    (horizontal strip)
```

## Avatar Customization

To customize the programmatic avatar, edit the `colors` object in `demo.js`:

```javascript
const colors = {
    skin: '#f5d0c5',      // Base skin color
    skinShadow: '#e8b4a6', // Skin shadow
    hair: '#2d1810',       // Hair color
    hairHighlight: '#4a2820', // Hair highlight
    eye: '#3d5a80',        // Iris color
    eyeWhite: '#f8f8f8',   // Eye white
    eyePupil: '#1a1a2e',   // Pupil color
    eyebrow: '#2d1810',    // Eyebrow color
    lipOuter: '#c77b7b',   // Outer lip color
    lipInner: '#a85555',   // Inner lip/mouth color
    teeth: '#f5f5f5',      // Teeth color
    tongue: '#d4777a',     // Tongue color
    background: '#1a1a25', // Canvas background
};
```
