import { useEffect, useRef, useState } from "react";
import { readLevel } from "../../hooks/useAudioRecorder";
import "./domain.css";

/*
 * The interview's presence indicator: a particle orb.
 *
 * Recreated from the WebGL orb in docs/reference/animation.txt. Its `hash33` and `snoise3`
 * are kept verbatim, because that noise is what gives the motion its
 * character - but they drive a real particle field here rather than a
 * fragment-shader glow. A few thousand points are distributed over a
 * sphere and pushed through a noise flow field, so the particles visibly
 * slide across and through the form instead of a texture scrolling behind
 * a circle.
 *
 * Two things are adapted rather than copied:
 *
 * 1. **No library.** The original pulls in `ogl`. This is one points draw
 *    and one halo quad in raw WebGL, so package.json is untouched.
 *
 * 2. **Rubric's palette.** The original runs purple/cyan/deep-blue through
 *    a hue rotation, which on a light canvas is the neon "AI orb" look
 *    design-system.md section 22 rules out. Here every particle is the
 *    indigo accent, and depth is carried by atmospheric perspective: near
 *    particles hold the accent, far ones fade toward the canvas. That is
 *    what makes it read as a volume on a light background rather than as
 *    a flat spray of dots.
 *
 * It never replaces the recording indicator. The live dot and the level
 * meter still say, explicitly and in text, that the microphone is on - a
 * candidate must never have to read an animation to know whether they are
 * being recorded.
 */

export type OrbState = "idle" | "listening" | "processing" | "speaking";

interface VoiceOrbProps {
  state: OrbState;
  /** Live analyser, read every frame while listening. */
  analyser: React.RefObject<AnalyserNode | null>;
  /** Increment to kick the orb: a spoken word, or a new question landing. */
  impulse?: number;
  size?: number;
}

/** Dense enough to read as a surface, sparse enough to stay elegant. */
const PARTICLE_COUNT = 5200;

/** Per-state targets. JS eases toward these so state changes glide rather
 *  than snap; the shaders themselves have no notion of state. */
const PRESETS: Record<OrbState, { intensity: number; speed: number; react: number }> = {
  // Present and slowly turning. Something is here and it is waiting.
  idle: { intensity: 1.0, speed: 0.26, react: 0.0 },
  // Alive. Amplitude comes straight from the microphone.
  listening: { intensity: 1.25, speed: 0.62, react: 1.0 },
  // Working, not listening. The field churns faster and tightens, but
  // nothing pretends to respond to sound that is not arriving.
  processing: { intensity: 1.05, speed: 1.05, react: 0.0 },
  // The system is talking. Pulses come from real word-boundary events.
  speaking: { intensity: 1.12, speed: 0.42, react: 0.9 },
};

/** hash33 and snoise3 are from docs/reference/animation.txt, unchanged. */
const NOISE = `
vec3 hash33(vec3 p3) {
  p3 = fract(p3 * vec3(0.1031, 0.11369, 0.13787));
  p3 += dot(p3, p3.yxz + 19.19);
  return -1.0 + 2.0 * fract(vec3(p3.x + p3.y, p3.x + p3.z, p3.y + p3.z) * p3.zyx);
}

float snoise3(vec3 p) {
  const float K1 = 0.333333333;
  const float K2 = 0.166666667;
  vec3 i = floor(p + (p.x + p.y + p.z) * K1);
  vec3 d0 = p - (i - (i.x + i.y + i.z) * K2);
  vec3 e = step(vec3(0.0), d0 - d0.yzx);
  vec3 i1 = e * (1.0 - e.zxy);
  vec3 i2 = 1.0 - e.zxy * (1.0 - e);
  vec3 d1 = d0 - (i1 - K2);
  vec3 d2 = d0 - (i2 - K1);
  vec3 d3 = d0 - 0.5;
  vec4 h = max(0.6 - vec4(dot(d0, d0), dot(d1, d1), dot(d2, d2), dot(d3, d3)), 0.0);
  vec4 n = h * h * h * h * vec4(
    dot(d0, hash33(i)), dot(d1, hash33(i + i1)),
    dot(d2, hash33(i + i2)), dot(d3, hash33(i + 1.0))
  );
  return dot(vec4(31.316), n);
}
`;

const PARTICLE_VERTEX = `
precision highp float;

attribute float aIndex;

uniform float uCount;
uniform float uTime;
uniform float uLevel;
uniform float uSpeed;
uniform float uDpr;
uniform float uPointScale;

varying float vNear;
varying float vSeed;
varying float vFlow;
varying float vFringe;
varying float vSize;

${NOISE}

/* Evenly spread points over a sphere. A random distribution clumps, and
   clumping is exactly what makes a particle field look cheap. */
vec3 fibonacciSphere(float i, float n) {
  float k = i + 0.5;
  float phi = acos(1.0 - 2.0 * k / n);
  float theta = 3.14159265359 * (1.0 + 2.2360679775) * k;
  return vec3(cos(theta) * sin(phi), sin(theta) * sin(phi), cos(phi));
}

void main() {
  vec3 dir = fibonacciSphere(aIndex, uCount);
  float seed = fract(sin(aIndex * 12.9898) * 43758.5453);

  float t = uTime * uSpeed;

  /* Particles sit at varying depths rather than all on one shell, so the
     orb has an interior and reads as a volume. The tail reaches past 1.0
     so the silhouette dissolves into the canvas instead of ending on a
     hard circle, which is what makes a particle ball look like a ball. */
  float shell = 0.54 + 0.50 * pow(seed, 0.62);
  float fringe = 1.0 - smoothstep(0.96, 1.04, shell);

  /* Three offset samples of the same noise make a smooth vector field.
     Particles slide along it, which is what produces flow rather than
     each point jittering independently in place. */
  vec3 q = dir * 1.35 + vec3(0.0, 0.0, t * 0.4);
  vec3 flow = vec3(snoise3(q), snoise3(q + 19.7), snoise3(q + 43.3));

  float amp = 0.17 + 0.34 * uLevel;
  vec3 pos = normalize(dir + flow * amp) * shell;

  /* How strongly this particle is being carried by the field. Feeding it
     into brightness is what turns a uniform speckle into visible currents:
     particles moving together light up together, so the eye reads streams
     through the volume rather than static noise. */
  vFlow = clamp(length(flow) * 0.62, 0.0, 1.0);

  /* Slow rotation about Y so the whole field turns and the silhouette
     never sits still. */
  float a = t * 0.2;
  mat3 rot = mat3(cos(a), 0.0, -sin(a), 0.0, 1.0, 0.0, sin(a), 0.0, cos(a));
  pos = rot * pos;

  float radius = 0.74 + 0.02 * sin(uTime * 0.8) + 0.17 * uLevel;
  pos *= radius;

  /* Weak perspective: near particles grow, far ones shrink. Enough to
     read as depth, not enough to look like a 3D demo. */
  float persp = 1.0 / (1.55 - pos.z * 0.5);
  vNear = pos.z * 0.5 + 0.5;
  vSeed = seed;
  vFringe = fringe;

  gl_Position = vec4(pos.xy * persp * 1.62, 0.0, 1.0);
  float sizeMix = 0.55 + 0.45 * seed + 1.5 * pow(seed, 6.0) + 0.3 * vFlow;
  vSize = sizeMix;
  gl_PointSize = uPointScale * uDpr * persp * sizeMix * (0.92 + 0.4 * uLevel);
}
`;

const PARTICLE_FRAGMENT = `
precision highp float;

varying float vNear;
varying float vSeed;
varying float vFlow;
varying float vFringe;
varying float vSize;

uniform vec3 uAccent;
uniform float uIntensity;

void main() {
  vec2 c = gl_PointCoord - 0.5;
  float d = length(c);
  if (d > 0.5) discard;

  /* A gaussian-ish falloff, not a disc with a feathered rim. Squaring it
     puts most of the weight at the centre, so overlapping particles build
     into a soft field rather than a grid of visible dots. */
  float soft = 1.0 - smoothstep(0.0, 0.5, d);
  soft = pow(soft, 1.3);

  /* Atmospheric perspective, inverted for a light canvas: distant
     particles fade toward the background rather than toward black. The
     range is wide on purpose - a narrow one gives an even grey haze with
     no front surface, which is what makes a particle ball look like dust. */
  vec3 far = mix(uAccent, vec3(1.0), 0.44);
  vec3 near = mix(uAccent, vec3(0.10, 0.08, 0.34), 0.3);
  vec3 color = mix(far, near, pow(vNear, 1.2));

  float alpha = soft * mix(0.14, 1.0, pow(vNear, 1.35)) * uIntensity;
  /* Currents read brighter than the still parts of the field. */
  alpha *= 0.5 + 0.85 * vFlow;
  /* Larger particles are a little fainter, the way an out-of-focus point
     is. Kept weak: divide by size in full and the field disappears. */
  alpha /= (0.88 + 0.28 * vSize);
  alpha *= vFringe;

  gl_FragColor = vec4(color, alpha);
}
`;

const HALO_VERTEX = `
precision highp float;
attribute vec2 aPosition;
varying vec2 vUv;
void main() {
  vUv = aPosition * 0.5 + 0.5;
  gl_Position = vec4(aPosition, 0.0, 1.0);
}
`;

const HALO_FRAGMENT = `
precision highp float;

varying vec2 vUv;
uniform float uLevel;
uniform float uIntensity;
uniform vec3 uAccent;

void main() {
  vec2 p = (vUv - 0.5) * 2.0;
  float d = length(p);

  /* One soft radial, well under the particles in strength. This is the
     atmosphere the field sits in; it is not a bloom, and it never has a
     visible edge. */
  float halo = exp(-d * 2.6) * (1.0 - smoothstep(0.30, 1.0, d));
  float alpha = halo * (0.13 + 0.16 * uLevel) * uIntensity;

  gl_FragColor = vec4(uAccent, alpha);
}
`;

function compile(gl: WebGLRenderingContext, type: number, source: string) {
  const shader = gl.createShader(type);
  if (!shader) return null;
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    gl.deleteShader(shader);
    return null;
  }
  return shader;
}

function link(gl: WebGLRenderingContext, vertexSource: string, fragmentSource: string) {
  const vertex = compile(gl, gl.VERTEX_SHADER, vertexSource);
  const fragment = compile(gl, gl.FRAGMENT_SHADER, fragmentSource);
  const program = gl.createProgram();
  if (!vertex || !fragment || !program) return null;
  gl.attachShader(program, vertex);
  gl.attachShader(program, fragment);
  gl.linkProgram(program);
  gl.deleteShader(vertex);
  gl.deleteShader(fragment);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    gl.deleteProgram(program);
    return null;
  }
  return program;
}

/** Reads a CSS custom property as a 0..1 rgb triple. The orb takes its
 *  color from the token layer rather than hardcoding one. */
function tokenColor(name: string, fallback: [number, number, number]) {
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const hex = raw.replace("#", "");
  if (hex.length !== 6) return fallback;
  const value = Number.parseInt(hex, 16);
  if (Number.isNaN(value)) return fallback;
  return [((value >> 16) & 255) / 255, ((value >> 8) & 255) / 255, (value & 255) / 255] as [
    number,
    number,
    number,
  ];
}

export function VoiceOrb({ state, analyser, impulse = 0, size = 280 }: VoiceOrbProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  /** False once we know this browser cannot draw the orb. */
  const [supported, setSupported] = useState(true);
  /** Decaying kick from the latest impulse. Read by the render loop. */
  const impulseRef = useRef(0);
  const stateRef = useRef<OrbState>(state);

  stateRef.current = state;

  useEffect(() => {
    if (impulse > 0) impulseRef.current = 1;
  }, [impulse]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const gl = canvas.getContext("webgl", {
      alpha: true,
      premultipliedAlpha: false,
      antialias: true,
    });
    // No WebGL is not worth surfacing: the meter, the timer and the
    // captions carry every piece of information on this screen. But the
    // canvas has to come out of the DOM entirely, because left in place it
    // renders as an opaque block in the middle of the interview.
    if (!gl) {
      setSupported(false);
      return;
    }

    const haloProgram = link(gl, HALO_VERTEX, HALO_FRAGMENT);
    const particleProgram = link(gl, PARTICLE_VERTEX, PARTICLE_FRAGMENT);
    if (!haloProgram || !particleProgram) {
      setSupported(false);
      return;
    }

    // Halo geometry: one triangle covering the viewport.
    const haloBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, haloBuffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);

    // Particle geometry: nothing but an index per point. Every position is
    // derived on the GPU, so there is no per-frame buffer upload at all.
    const indices = new Float32Array(PARTICLE_COUNT);
    for (let i = 0; i < PARTICLE_COUNT; i += 1) indices[i] = i;
    const particleBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, particleBuffer);
    gl.bufferData(gl.ARRAY_BUFFER, indices, gl.STATIC_DRAW);

    const halo = {
      position: gl.getAttribLocation(haloProgram, "aPosition"),
      level: gl.getUniformLocation(haloProgram, "uLevel"),
      intensity: gl.getUniformLocation(haloProgram, "uIntensity"),
      accent: gl.getUniformLocation(haloProgram, "uAccent"),
    };
    const particle = {
      index: gl.getAttribLocation(particleProgram, "aIndex"),
      count: gl.getUniformLocation(particleProgram, "uCount"),
      time: gl.getUniformLocation(particleProgram, "uTime"),
      level: gl.getUniformLocation(particleProgram, "uLevel"),
      speed: gl.getUniformLocation(particleProgram, "uSpeed"),
      dpr: gl.getUniformLocation(particleProgram, "uDpr"),
      pointScale: gl.getUniformLocation(particleProgram, "uPointScale"),
      accent: gl.getUniformLocation(particleProgram, "uAccent"),
      intensity: gl.getUniformLocation(particleProgram, "uIntensity"),
    };

    const accent = tokenColor("--color-accent", [0.31, 0.275, 0.898]);
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = size * ratio;
    canvas.height = size * ratio;
    gl.viewport(0, 0, canvas.width, canvas.height);

    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    gl.clearColor(0, 0, 0, 0);

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    // Point size is in device pixels, so it scales with the orb rather
    // than staying a fixed dot as the canvas shrinks on a phone.
    const pointScale = (size / 280) * 8.2;

    const current = { ...PRESETS[stateRef.current] };
    let smoothedLevel = 0;
    let frame = 0;
    const startedAt = performance.now();

    function render(elapsed: number, level: number) {
      if (!gl || !haloProgram || !particleProgram) return;
      gl.clear(gl.COLOR_BUFFER_BIT);

      gl.useProgram(haloProgram);
      gl.bindBuffer(gl.ARRAY_BUFFER, haloBuffer);
      gl.enableVertexAttribArray(halo.position);
      gl.vertexAttribPointer(halo.position, 2, gl.FLOAT, false, 0, 0);
      gl.uniform3f(halo.accent, accent[0], accent[1], accent[2]);
      gl.uniform1f(halo.level, level);
      gl.uniform1f(halo.intensity, current.intensity);
      gl.drawArrays(gl.TRIANGLES, 0, 3);

      gl.useProgram(particleProgram);
      gl.bindBuffer(gl.ARRAY_BUFFER, particleBuffer);
      gl.enableVertexAttribArray(particle.index);
      gl.vertexAttribPointer(particle.index, 1, gl.FLOAT, false, 0, 0);
      gl.uniform1f(particle.count, PARTICLE_COUNT);
      gl.uniform1f(particle.time, elapsed);
      gl.uniform1f(particle.level, level);
      gl.uniform1f(particle.speed, current.speed);
      gl.uniform1f(particle.dpr, ratio);
      gl.uniform1f(particle.pointScale, pointScale);
      gl.uniform1f(particle.intensity, current.intensity);
      gl.uniform3f(particle.accent, accent[0], accent[1], accent[2]);
      gl.drawArrays(gl.POINTS, 0, PARTICLE_COUNT);
    }

    function loop(now: number) {
      const elapsed = (now - startedAt) / 1000;
      const target = PRESETS[stateRef.current];

      const ease = 0.05;
      current.intensity += (target.intensity - current.intensity) * ease;
      current.speed += (target.speed - current.speed) * ease;
      current.react += (target.react - current.react) * ease;

      // Real in both reactive states, from different sources: microphone
      // amplitude while listening, word-boundary events while speaking.
      // Neither is synthesised.
      let raw = 0;
      if (stateRef.current === "listening" && analyser.current) {
        raw = readLevel(analyser.current);
      } else if (stateRef.current === "speaking") {
        raw = impulseRef.current;
      }
      impulseRef.current *= 0.93;

      // Asymmetric smoothing: rise fast so a syllable registers, fall slow
      // so the field settles instead of strobing.
      const rate = raw > smoothedLevel ? 0.32 : 0.07;
      smoothedLevel += (raw - smoothedLevel) * rate;

      render(elapsed, smoothedLevel * current.react);
      frame = requestAnimationFrame(loop);
    }

    if (reduceMotion) {
      // design-system.md section 18 rules out looping ambient animation for
      // anyone who has asked for less of it. One frame, then still.
      render(0, 0);
    } else {
      frame = requestAnimationFrame(loop);
    }

    return () => {
      cancelAnimationFrame(frame);
      gl.deleteBuffer(haloBuffer);
      gl.deleteBuffer(particleBuffer);
      gl.deleteProgram(haloProgram);
      gl.deleteProgram(particleProgram);
      // Deliberately NOT calling WEBGL_lose_context. A canvas hands out one
      // context for its lifetime, and React reuses the element across a
      // remount - StrictMode every time in development, a resize in
      // production. Losing it here meant the next mount got the dead
      // context back and the orb silently never drew again.
    };
  }, [analyser, size]);

  if (!supported) return null;

  return (
    <canvas
      ref={canvasRef}
      className="rb-orb"
      style={{ width: size, height: size }}
      // Decorative. Every state it depicts is also stated in text beside it.
      aria-hidden="true"
    />
  );
}
