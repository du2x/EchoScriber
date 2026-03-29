# PRD — Linux Realtime Speech-to-Text (Mic + Audio Board) with Echo Cancellation and Simple GUI

## 1. Overview

Build a Linux desktop application that performs realtime speech-to-text from:

* **Microphone input**
* **System / audio-board playback input**

The product should provide:

* **Low-latency transcription**
* **Echo cancellation** so microphone capture is not polluted by local playback
* **Simple GUI** for device selection, start/stop, status, and transcript display
* **Local-first execution** as the default operating mode

Working title: **EchoScribe**

---

## 2. Problem Statement

Linux users often need live transcription from microphones and system audio, but current solutions are fragmented:

* microphone capture and loopback/system capture are separate problems
* echo cancellation usually requires manual audio graph setup
* many speech models are accurate but not optimized for realtime desktop UX
* existing tools are often CLI-first, not simple GUI products

The goal is to provide a single desktop app that makes realtime transcription practical for meetings, calls, demos, interviews, livestream monitoring, and note-taking.

---

## 3. Product Goals

### Primary goals

1. Transcribe speech in near realtime from **mic** and **system playback loopback**.
2. Reduce or eliminate local playback echo from microphone-derived transcripts.
3. Provide a **simple Linux-native GUI**.
4. Work offline by default, with optional pluggable engines later.
5. Be robust across common Linux desktop environments using PipeWire/Pulse compatibility.
6. Optimize for **developer tooling workflows** first.
7. Use **GPU acceleration as the primary performance assumption**.

### Non-goals (MVP)

* Speaker diarization
* Translation
* Cloud sync
* Editing transcripts collaboratively
* Full meeting assistant features (summaries, action items)
* Windows/macOS support

---

## 4. Target Users

### Primary users

* Developers and technical users on Linux
* Engineers transcribing calls, demos, debugging sessions, and screen recordings
* Accessibility users needing live captions
* Content creators monitoring mic + system audio

### Secondary users

* Journalists / researchers recording interviews
* Support/ops teams transcribing calls or demos
* Students transcribing lectures or remote classes

## 5. Core Use Cases

1. **Mic transcription**

   * User selects microphone and clicks Start.
   * App shows live transcript with low latency.

2. **System playback transcription**

   * User selects a playback monitor / loopback source.
   * App transcribes audio currently being played by the Linux system.

3. **Mic + local playback with echo cancellation**

   * User is on a call, watching a demo, or listening to remote audio through speakers.
   * App captures the mic while canceling the playback reference from the transcript path.

4. **Dual-source developer workflow**

   * User runs two inputs simultaneously and can view tagged transcript lines while coding, debugging, or taking technical notes.

5. **Quick note-taking from technical sessions**

   * User copies transcript text or saves to file after a meeting, incident review, or demo.

## 6. User Stories

* As a Linux user, I want to choose my audio input and start transcription in one click.
* As a podcaster or interviewer, I want to transcribe both my mic and board audio.
* As a remote worker, I want the app to avoid transcribing my speakers through my mic.
* As a technical user, I want to see audio levels and know whether capture is healthy.
* As an accessibility user, I want large live captions with minimal setup.
* As a privacy-conscious user, I want transcription to run locally.

---

## 7. Functional Requirements

### 7.1 Audio Inputs

* Enumerate available audio devices and logical sources.
* Support at least:

  * microphone input
  * PipeWire/Pulse playback monitor source / loopback source
* Allow user to select:

  * Mic source
  * Playback reference source
  * STT source mode: mic / system / both
* System audio support should be designed around **Linux playback loopback**, not generic external board capture.

### 7.2 Echo Cancellation

* Provide **Echo Cancellation: On/Off** toggle.
* When enabled for mic mode:

  * app should use playback/render audio as reference signal
  * app should remove or attenuate playback echo from mic stream before STT
* Show status:

  * enabled
  * reference available / unavailable
  * degraded
* Offer fallback when AEC is unavailable:

  * warning message
  * continue without AEC

### 7.3 Speech-to-Text

* Realtime partial transcript updates.
* Finalized transcript segments.
* Configurable language.
* Initial language support:

  * Portuguese (Brazil)
  * English
* Word timestamps optional in MVP if backend supports them.
* Support hot-swapping among installed local models.
* Optimize inference around GPU acceleration as the default performance path.

### 7.4 Transcript UI

* Live scrolling transcript pane.
* Partial lines visually distinct from final lines.
* Source tags per segment:

  * MIC
  * SYSTEM
* Copy selected text.
* Clear transcript.
* Save transcript to TXT/Markdown.

### 7.5 Session Controls

* Start / Stop / Pause.
* Device re-scan.
* Basic settings dialog.
* Show current model, latency estimate, and CPU/GPU usage summary.

### 7.6 Diagnostics

* Audio level meter for each source.
* Error states:

  * no input signal
  * device disconnected
  * model load failure
  * unsupported sample rate
  * AEC reference missing
* Export debug log.

---

## 8. Non-Functional Requirements

### 8.1 Performance

* Partial transcript latency target: **< 2 s** on supported GPU-equipped hardware.
* Final segment emission target: **1–3 s** depending on model and hardware.
* App startup to ready: **< 5 s** excluding first model download.

### 8.2 Resource Profile

* GPU acceleration is assumed for primary deployments.

* CPU-only mode may exist as fallback or dev mode, but it is not the main sizing assumption.

* Prefer efficient local inference with good VRAM discipline.

* Must run on Linux desktops without dedicated GPU.

* Prefer CPU-only workable mode for small models.

* Use GPU acceleration when available.

### 8.3 Reliability

* App should survive device hotplug and recover when possible.
* A long-running session target: **4+ hours** without restart.

### 8.4 Privacy

* Default mode is fully local.
* No transcript leaves the machine unless explicitly enabled in future versions.

### 8.5 UX

* New user should complete first transcription in **under 2 minutes**.
* Main window should remain simple and non-technical by default.

---

## 9. UX / GUI Proposal

### Main window

* Top bar:

  * Source mode dropdown: Mic / System / Both
  * Start / Stop button
  * Status indicator
* Left panel:

  * Mic device selector
  * Playback loopback selector
  * Echo cancellation toggle
  * Language selector
  * Model selector
* Center panel:

  * Live transcript
* Bottom bar:

  * latency
  * audio activity
  * warnings/errors

### Advanced settings (collapsible or separate dialog)

* Chunk size / buffering
* VAD sensitivity
* Partial transcript mode
* Timestamp toggle
* Save path
* Debug logging

### Accessibility

* Keyboard navigable
* Large-text transcript mode
* High contrast theme support

---

## 10. Technical Product Direction

### Recommended architecture

**Audio pipeline**

1. Capture mic stream
2. Capture playback/render reference stream
3. Apply AEC/noise processing to mic path
4. Run VAD/segmentation
5. Feed streaming chunks to STT engine
6. Emit partial/final transcript events to GUI

### Candidate implementation stack

#### Option A — Python desktop app (recommended for fastest MVP)

* GUI: PySide6 / Qt
* Audio I/O: PipeWire integration via subprocess / bindings, or Pulse-compatible monitor sources
* DSP/AEC: PipeWire echo-cancel path or WebRTC audio processing binding
* STT: faster-whisper or Vosk fallback
* GPU inference: CUDA-backed path where supported
* Packaging: AppImage / deb / flatpak later

**Pros**

* Fastest iteration
* Strong AI/audio ecosystem
* Easier model integration

**Cons**

* More care needed for packaging and native audio edge cases

#### Option B — Rust desktop app

* GUI: Tauri or egui
* Audio: CPAL + PipeWire/native bindings
* DSP/AEC: webrtc-audio-processing crate/bindings
* STT: Whisper/CTranslate2 bridge or Vosk binding
* GPU inference: native/runtime-specific integration depending on backend choice

**Pros**

* Strong binary distribution story
* Lower runtime footprint

**Cons**

* Slower initial product iteration
* More integration complexity for STT stack

### MVP recommendation

Use **Python + PySide6 + faster-whisper + PipeWire/WebRTC AEC**.
Target the MVP at **GPU-equipped Linux developer workstations**.

---

## 11. Supported Audio Modes

### Mode 1: Mic only

* Capture mic
* Optional AEC if playback reference exists
* Realtime transcript output

### Mode 2: System playback loopback only

* Capture monitor/loopback source
* No AEC needed
* Realtime transcript output

### Mode 3: Both

* Process mic and system streams independently
* Show tagged transcript lines
* Optional merge view

---

## 12. Model Strategy

### Default model tiers

* **Small / fast**: for low-latency GPU usage and fallback scenarios
* **Medium**: balanced accuracy and speed
* **Larger optional**: higher accuracy on stronger developer workstations

Priority should be given to model/runtime combinations that behave well for:

* Portuguese (Brazil)
* English
* code-switching tolerance between the two languages

### HuggingFace models

HuggingFace Hub hosts community fine-tunes of Whisper (and other ASR models) specifically trained on PT-BR corpora that significantly outperform base Whisper models for that language. These should be evaluated alongside the default Whisper model tiers.

**Integration approach:**

* `faster-whisper` supports loading HuggingFace Hub models directly (`WhisperModel("username/model-id", ...)`), covering models that have been converted to CTranslate2 format.
* For fine-tuned models only available in `transformers` format (not yet converted), implement a second `STTEngine` adapter backed by `transformers.pipeline("automatic-speech-recognition")`. This trades some inference speed for access to a wider set of PT-BR fine-tunes.
* Expose both adapters as selectable backends in the UI model dropdown. Default to faster-whisper for lower latency; allow the user to switch to a HuggingFace transformers model for higher PT-BR accuracy.

### Engine abstraction

Design a backend interface so multiple STT engines can be swapped:

* `start()`
* `stop()`
* `push_audio(chunk, source_id)`
* `on_partial(callback)`
* `on_final(callback)`
* `list_models()`

This reduces lock-in and allows experimentation.

---

## 13. Success Metrics

### MVP success

* User can install and transcribe from mic in under 10 minutes.
* User can transcribe Linux system playback loopback on mainstream PipeWire distributions.
* Echo leakage into mic transcripts is materially reduced in common desktop conditions.
* Median partial latency under 2 seconds on target GPU-equipped hardware.
* The tool feels usable for real developer workflows: calls, demos, debugging, and technical note capture.

### Product quality metrics

* Crash-free session rate
* Device detection success rate
* AEC setup success rate
* Word error rate on internal test corpus
* User-perceived latency satisfaction

---

## 14. Risks and Mitigations

### Risk 1: Linux audio graph variability

Different distros and desktop setups expose devices differently.
**Mitigation:** build around PipeWire/Pulse-compatible source discovery and test on Ubuntu, Fedora, Arch.

### Risk 2: Echo cancellation quality is environment-dependent

AEC depends on stable playback reference, latency alignment, and acoustic conditions.
**Mitigation:** use dedicated reference capture path, expose diagnostics, and define clear “best with headphones” guidance.

### Risk 3: GPU/runtime compatibility on Linux

Linux GPU inference stacks can be fragile across drivers, CUDA versions, and packaging formats.
**Mitigation:** define a narrow support matrix early, validate on target NVIDIA-based environments first, and keep a CPU fallback for degraded mode.

### Risk 4: Simultaneous dual-stream transcription complexity

**Mitigation:** support independent pipelines with a simple transcript merge strategy.

### Risk 5: Packaging and permissions on Linux

**Mitigation:** prioritize AppImage for early distribution; document PipeWire prerequisites.

---

## 15. MVP Scope

### In scope

* Linux desktop app
* Mic transcription
* System playback loopback transcription
* Basic echo cancellation for mic path
* Live transcript view
* Save/copy transcript
* Device selection
* Local model execution
* Portuguese (Brazil) and English language support
* Developer-oriented diagnostics and controls

### Out of scope

* Speaker diarization
* Cloud transcription
* Meeting summaries
* Translation
* Wake word / voice commands
* Multi-user collaboration

---

## 16. Post-MVP Roadmap

### Phase 2

* Speaker diarization
* Summaries / notes export
* Per-app audio capture selection
* Hotkeys / push-to-talk
* Subtitle overlay mode

### Phase 3

* Translation
* Remote streaming API
* Plugin architecture
* Meeting assistant features

---

## 17. Milestones

### Milestone 1 — Technical spike

* Validate PipeWire device discovery
* Validate mic capture
* Validate playback loopback capture
* Validate AEC path with playback reference
* Benchmark GPU-backed STT engines for Portuguese (Brazil) and English

### Milestone 2 — Alpha CLI pipeline

* End-to-end audio → AEC → VAD → STT working from terminal
* Partial/final transcript events implemented

### Milestone 3 — GUI MVP

* Simple desktop window
* Device selectors
* Start/stop
* Transcript pane
* Save/export

### Milestone 4 — Beta hardening

* Distros testing
* Device hotplug
* Logs/diagnostics
* Packaging

---

## 18. Acceptance Criteria (MVP)

1. User can launch app, choose microphone, and see live transcript.
2. User can choose system playback loopback source and transcribe playback audio.
3. With AEC enabled and reference configured, mic transcript contains substantially less speaker playback bleed than without AEC in test scenarios.
4. User can switch between Portuguese (Brazil) and English.
5. User can save transcript to disk.
6. App handles device disconnects gracefully.
7. App remains responsive during 30-minute sessions on target GPU-equipped Linux machines.

## 19. Resolved Product Decisions

1. **GPU acceleration** is assumed.

   * The primary runtime path should take advantage of GPU inference when available on the target Linux machine.
   * CPU-only fallback is helpful for development and degraded mode, but GPU-backed performance is a planning assumption, not an optional bonus.

2. The product is **developer tooling first**.

   * Primary positioning: a practical desktop utility for developers who need live transcription from mic and system audio during calls, demos, debugging sessions, screen recordings, and technical note-taking.
   * UX should therefore prioritize reliability, inspectability, device/control transparency, and fast iteration over mass-market polish.

3. Initial language scope is:

   * **Portuguese (Brazil)**
   * **English**
   * Language selection should be explicit in the UI, with optional future auto-detection.

4. **Audio board** means **system playback loopback**.

   * The system-audio input path should therefore be designed specifically around Linux playback monitor / loopback capture.
   * External USB audio interface capture is not a core MVP requirement unless it appears naturally as a standard system capture/monitor source.

5. The application should optimize for the specific dual-developer workflow:

   * transcribing local mic speech
   * transcribing system playback
   * reducing system playback bleed into mic transcripts via AEC

## 20. Recommended Next Step Recommended Next Step

Start with a **technical spike** to de-risk three things first:

1. PipeWire capture of mic + system audio
2. practical echo cancellation quality
3. realtime latency of the chosen STT backend on target hardware

If those three are validated, the product is highly feasible as a Linux desktop MVP.

---

## 21. Proposed Technical Architecture

### 21.1 High-level architecture

The MVP should be split into six runtime subsystems:

1. **GUI layer**

   * Main window
   * Device selectors
   * Transcript view
   * Status / diagnostics
   * Settings panel

2. **Session controller**

   * Orchestrates app state
   * Applies configuration
   * Starts/stops pipelines
   * Handles errors and recovery

3. **Audio capture layer**

   * Mic capture
   * System playback loopback capture
   * Device enumeration and health monitoring

4. **Audio processing layer**

   * Resampling
   * Channel normalization
   * Frame buffering
   * Echo cancellation on mic path
   * Optional VAD / denoise / gain normalization

5. **STT engine layer**

   * Streaming chunk ingestion
   * Partial transcript generation
   * Final segment generation
   * Language/model selection
   * GPU runtime management

6. **Persistence + diagnostics layer**

   * Session logs
   * Transcript save/export
   * Debug bundle export
   * Runtime metrics

### 21.2 Suggested module boundaries

#### `app.gui`

Owns Qt windows, widgets, event wiring, transcript rendering, and user commands.

#### `app.session`

Owns the application state machine and coordinates the lifecycle of audio and STT pipelines.

#### `app.audio.discovery`

Enumerates PipeWire/Pulse-compatible devices and logical monitor sources.

#### `app.audio.capture`

Creates and maintains input streams for:

* mic
* playback loopback

#### `app.audio.processing`

Applies resampling, buffering, frame alignment, and AEC-related processing.

#### `app.audio.vad`

Optional voice activity detection for segmentation and compute reduction.

#### `app.stt`

Abstract interface for STT backends plus concrete implementation(s), initially faster-whisper.

#### `app.transcript`

Stores partial/final segments, source tags, timestamps, and export formatting.

#### `app.diagnostics`

Captures runtime counters, device issues, latency estimates, and error traces.

#### `app.config`

Persists user settings such as selected language, model, devices, and AEC preferences.

### 21.3 Recommended runtime state machine

The session controller should use an explicit state machine:

* `idle`
* `loading_model`
* `ready`
* `starting`
* `running`
* `paused`
* `degraded`
* `error`
* `stopping`

This avoids brittle implicit UI state and makes recovery logic much easier.

### 21.4 Audio pipeline design

#### Mic path

1. Read mic frames
2. Resample to STT/AEC working format
3. Apply playback-reference alignment
4. Apply AEC
5. Apply optional VAD / cleanup
6. Push speech frames to STT stream
7. Emit transcript events tagged `MIC`

#### System playback path

1. Read loopback/monitor frames
2. Resample to STT working format
3. Optionally apply VAD
4. Push speech frames to STT stream
5. Emit transcript events tagged `SYSTEM`

#### Playback reference path for AEC

* The loopback source used for transcription can also serve as the AEC render reference.
* The product should treat transcription input and AEC reference as separate logical consumers, even when they originate from the same monitor source.

### 21.5 Concurrency model

Use separate worker components for:

* GUI thread
* Mic capture worker
* System capture worker
* Audio processing/AEC worker
* STT inference worker
* Diagnostics/logging worker

For Python, the cleanest MVP is usually:

* Qt main thread for UI
* `QThread` or standard worker threads for capture and orchestration
* bounded queues between stages
* careful backpressure handling to avoid transcript lag explosion

### 21.6 Backpressure strategy

The system must explicitly handle overload. Recommended policy:

* Keep small bounded buffers per source
* Prefer dropping oldest partial-audio backlog rather than freezing UI
* Log when backpressure is happening
* Surface a “latency degraded” warning in the GUI

### 21.7 Transcript event model

Define transcript events as structured records:

* `source_id` (`mic` / `system`)
* `source_tag` (`MIC` / `SYSTEM`)
* `text`
* `is_partial`
* `segment_id`
* `start_time`
* `end_time`
* `language`
* `confidence` (optional)
* `created_at`

This makes later features easier: overlay captions, summaries, exports, or API mode.

### 21.8 Configuration model

Persist at least:

* selected mic device
* selected loopback source
* language
* selected model
* AEC enabled
* VAD enabled
* transcript save path
* window size / UI preferences
* debug logging enabled

### 21.9 Error handling policy

Classify errors into:

* **recoverable**: device temporary unavailable, monitor source disappeared, transient overload
* **degraded**: AEC unavailable, GPU unavailable so CPU fallback engaged, missing playback reference
* **fatal for session**: model failed to load, no usable input source, unrecoverable backend crash

The GUI should always tell the user:

* what failed
* whether transcription continues
* what functionality is degraded
* what action is suggested

### 21.10 Observability for a dev-first product

Expose a lightweight diagnostics panel with:

* current state
* source sample rate
* queue depth
* model name
* GPU/CPU mode
* partial latency estimate
* dropped-frame count
* AEC status
* VAD status

---

## 22. Candidate Stack Decision (ADR-lite)

### 22.1 Recommended MVP stack

* **Language:** Python
* **GUI:** PySide6
* **Audio integration:** PipeWire / Pulse-compatible source discovery and capture
* **AEC strategy:** PipeWire echo-cancel when feasible, with in-app fallback path later if needed
* **STT backend:** faster-whisper
* **Packaging target:** AppImage first
* **Primary hardware assumption:** NVIDIA GPU Linux workstation

### 22.2 Why this stack

This combination optimizes for:

* shortest time to MVP
* strong speech/AI ecosystem
* practical Linux developer adoption
* easier experimentation with models and segmentation logic

### 22.3 Tradeoffs accepted

* Python packaging complexity is accepted in exchange for faster delivery.
* PipeWire integration complexity is accepted because Linux loopback capture is central to the product.
* GPU runtime friction is accepted because GPU acceleration is a product assumption.

### 22.4 Explicit non-choice for MVP

Do **not** begin with a Rust rewrite-first strategy.
That may become attractive later, but it is not the best way to validate product feasibility quickly.

---

## 23. MVP Backlog (Prioritized)

### P0 — feasibility-critical

1. **Enumerate Linux audio sources**

   * list mic devices
   * list playback loopback/monitor sources
   * verify stable identifiers

2. **Capture mic audio reliably**

   * open stream
   * read frames continuously
   * expose level meter

3. **Capture system playback loopback reliably**

   * open monitor source
   * read frames continuously
   * expose level meter

4. **Load GPU-backed STT model**

   * model bootstrap
   * runtime validation
   * warmup path

5. **Realtime transcription from single source**

   * partial updates
   * final segments
   * PT-BR / EN language selection

6. **Mic AEC using playback reference**

   * configure reference path
   * compare on/off behavior
   * expose AEC status

7. **Simple GUI shell**

   * source selectors
   * start/stop
   * live transcript pane
   * status line

### P1 — MVP completion

8. **Dual-source mode**

   * mic + system simultaneously
   * tagged transcript lines

9. **Transcript controls**

   * clear
   * copy
   * save TXT/Markdown

10. **Settings persistence**

* remember devices, model, language, toggles

11. **Diagnostics panel**

* queue depth
* latency estimate
* AEC state
* dropped frames

12. **Recovery behavior**

* handle device disconnects
* restart failed stream when possible

13. **Basic packaging**

* repeatable local build
* AppImage packaging prototype

### P2 — immediately after MVP

14. **Pause/resume**
15. **Timestamp toggle**
16. **Large-text caption mode**
17. **Hotkeys**
18. **Session debug export**
19. **Optional CPU fallback mode**

---

## 24. Engineering Work Breakdown

### Track A — Audio platform

* device discovery abstraction
* mic capture implementation
* loopback capture implementation
* sample-rate normalization
* source hotplug handling

### Track B — Audio processing

* frame buffer abstraction
* AEC integration
* VAD integration
* overload handling and frame dropping policy

### Track C — STT engine

* backend interface
* faster-whisper adapter
* language switching
* partial/final event protocol
* GPU environment validation

### Track D — Desktop GUI

* main window
* transcript pane
* device/model/language controls
* diagnostics widgets
* settings dialog

### Track E — Persistence and logs

* settings store
* transcript export
* runtime logs
* debug bundle export

### Track F — QA and benchmarks

* latency benchmark harness
* PT-BR sample corpus smoke tests
* EN sample corpus smoke tests
* AEC comparison test procedure
* distro compatibility matrix

---

## 25. Proposed Repository Structure

```text
realtime-stt/
  app/
    gui/
    session/
    audio/
      discovery/
      capture/
      processing/
      vad/
    stt/
    transcript/
    diagnostics/
    config/
    utils/
  tests/
    unit/
    integration/
    fixtures/
  scripts/
  packaging/
  docs/
    prd/
    architecture/
    adrs/
    test-plans/
```

---

## 26. Definition of Done for the Technical Spike

A technical spike is successful only if all of the following are demonstrated:

1. Mic transcription works in realtime on Linux.
2. System playback loopback transcription works in realtime on Linux.
3. PT-BR and EN both produce acceptable transcript quality in smoke tests.
4. GPU-backed inference works on the chosen target environment.
5. AEC materially reduces playback bleed into the mic path in at least one repeatable test setup.
6. The app can run a 15-minute session without instability.

---

## 27. First 3 Implementation Sprints

### Sprint 1 — technical spike

Goal: de-risk audio capture, GPU inference, and AEC.

Deliverables:

* CLI mic capture test
* CLI loopback capture test
* CLI STT test for PT-BR and EN
* baseline latency measurements
* AEC on/off comparison notes

### Sprint 2 — alpha pipeline

Goal: end-to-end non-GUI product core.

Deliverables:

* session controller
* single-source transcription pipeline
* dual-source tagged events
* transcript object model
* structured logs

### Sprint 3 — GUI MVP

Goal: usable desktop application.

Deliverables:

* main window
* selectors and controls
* live transcript pane
* save/copy actions
* diagnostics strip
* basic settings persistence

---

## 28. Product Positioning Statement

**A Linux-first realtime transcription tool for developers that captures microphone and system playback, runs locally with GPU acceleration, and reduces speaker echo contamination through practical AEC.**

---

## 29. Immediate Next Build Target

Build a **CLI-first technical spike** before the full GUI.
That is the fastest route to validating the three real risks in this product:

* Linux loopback capture
* AEC effectiveness
* GPU realtime transcription performance
