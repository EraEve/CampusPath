/**
 * CampusPath — Search Animation Player
 *
 * Plays back algorithm search steps on the MapRenderer.
 * Supports play/pause, step forward/backward, and speed control.
 */

class AlgorithmAnimator {
    constructor(renderer) {
        this.renderer = renderer;
        this.steps = [];
        this.currentStep = -1;
        this.timerId = null;
        this.speed = 200;  // ms between steps
        this.isPlaying = false;
    }

    /** Load a new set of steps and reset */
    loadSteps(steps, path) {
        this.stop();
        this.steps = steps || [];
        this.finalPath = path || [];
        this.currentStep = -1;
        this._updateDisplay();
    }

    /** Start auto-playback */
    play() {
        if (this.steps.length === 0) {
            console.warn('No steps to play — find a path first.');
            return false;
        }
        if (this.currentStep >= this.steps.length - 1) {
            this.currentStep = -1;  // restart
        }
        this.isPlaying = true;
        this._scheduleNext();
        return true;
    }

    /** Pause playback */
    pause() {
        this.isPlaying = false;
        if (this.timerId) {
            clearTimeout(this.timerId);
            this.timerId = null;
        }
    }

    /** Stop and reset */
    stop() {
        this.pause();
        this.currentStep = -1;
        this._updateDisplay();
    }

    /** Advance one step forward */
    stepForward() {
        if (this.currentStep < this.steps.length - 1) {
            this.currentStep++;
            this._applyStep(this.currentStep);
        } else if (this.currentStep === this.steps.length - 1) {
            // Show final path
            this._showFinalPath();
        }
    }

    /** Go back one step */
    stepBackward() {
        if (this.currentStep > 0) {
            this.currentStep--;
            this._applyStep(this.currentStep);
        } else if (this.currentStep === 0) {
            this.currentStep = -1;
            this._updateDisplay();
        }
    }

    /** Set playback speed in ms */
    setSpeed(ms) {
        this.speed = Math.max(50, Math.min(2000, ms));
    }

    /** Jump to a specific step */
    goToStep(index) {
        if (index >= -1 && index < this.steps.length) {
            this.currentStep = index;
            if (index >= 0) {
                this._applyStep(index);
            } else {
                this._updateDisplay();
            }
        }
    }

    /** Total number of steps */
    totalSteps() {
        return this.steps.length;
    }

    // ---- Internal ----

    _scheduleNext() {
        if (!this.isPlaying) return;
        if (this.currentStep < this.steps.length - 1) {
            this.timerId = setTimeout(() => {
                this.currentStep++;
                this._applyStep(this.currentStep);
                this._scheduleNext();
            }, this.speed);
        } else {
            this.isPlaying = false;
            this._showFinalPath();
        }
    }

    _applyStep(index) {
        const step = this.steps[index];
        if (!step) return;

        const state = {};

        // Mark visited nodes
        if (step.visited) {
            for (const nid of step.visited) {
                state[nid] = 'visited';
            }
        }

        // Mark frontier nodes
        if (step.frontier) {
            for (const nid of step.frontier) {
                if (state[nid] !== 'visited') {
                    state[nid] = 'frontier';
                }
            }
        }

        // Mark current node
        if (step.current) {
            state[step.current] = 'current';
        }

        this.renderer.setState(state, []);
        this._updateCounter(index);
    }

    _showFinalPath() {
        const state = {};
        for (const nid of this.finalPath) {
            state[nid] = 'path';
        }
        this.renderer.setState(state, this.finalPath);
        this._updateCounter(this.steps.length);
    }

    _updateDisplay() {
        this.renderer.setState({}, []);
        this._updateCounter(-1);
    }

    _updateCounter(index) {
        const el = document.getElementById('anim-step-counter');
        if (el) {
            el.textContent = index >= 0
                ? `Step ${index + 1} / ${this.steps.length}`
                : 'Ready';
        }
    }
}
