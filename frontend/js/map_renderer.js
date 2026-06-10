/**
 * CampusPath — Canvas 2D Map Renderer
 *
 * Renders a single building floor on an HTML5 Canvas,
 * with layered drawing for nodes, edges, and algorithm
 * state overlays (start, goal, path, visited, frontier).
 *
 * Coordinate system:
 *   - JSON uses normalized (0-100, 0-60).
 *   - Canvas maps to pixel dimensions via DPR-aware scaling.
 */

class MapRenderer {
    constructor(canvas) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.floorData = null;
        this.state = {};          // node_id → 'normal'|'start'|'goal'|'path'|'visited'|'frontier'|'current'
        this.highlightPath = [];  // ordered node IDs on the path
        this.nodePositions = {};  // node_id → {x, y} in pixel coords

        // Scale factors: normalize 100×60 → canvas pixels
        this.scaleX = 1;
        this.scaleY = 1;
        this.offsetX = 0;
        this.offsetY = 0;

        this._resize();
        window.addEventListener('resize', () => this._resize());
    }

    /** Recalculate scale and offset on resize */
    _resize() {
        const dpr = window.devicePixelRatio || 1;
        const rect = this.canvas.getBoundingClientRect();
        this.canvas.width = rect.width * dpr;
        this.canvas.height = rect.height * dpr;
        this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

        // Map 100×60 normalized space → canvas pixels with padding
        const pad = 30;
        const w = rect.width - pad * 2;
        const h = rect.height - pad * 2;
        this.scaleX = w / 100;
        this.scaleY = h / 60;
        this.offsetX = pad;
        this.offsetY = pad;
    }

    /** Convert normalized (0-100, 0-60) → canvas pixel (x, y) */
    _toPixel(nx, ny) {
        return {
            x: nx * this.scaleX + this.offsetX,
            y: ny * this.scaleY + this.offsetY,
        };
    }

    // ---- Public API ----

    /** Load floor data from API and render */
    loadFloor(floorData) {
        this.floorData = floorData;
        this.state = {};
        this.highlightPath = [];
        this.nodePositions = {};
        this._computeNodePositions();
        this.render();
    }

    /** Set algorithm visualization state */
    setState(nodeStates, path) {
        this.state = nodeStates || {};
        this.highlightPath = path || [];
        this.render();
    }

    /** Full render: nodes + edges + overlays */
    render() {
        if (!this.floorData) return;
        const rect = this.canvas.getBoundingClientRect();
        this.ctx.clearRect(0, 0, rect.width, rect.height);

        this._drawEdges();
        this._drawNodes();
        this._drawPathHighlight();
        this._drawStateOverlay();
    }

    /** Hit-test: which node is at pixel (px, py)? */
    hitTest(px, py) {
        const rect = this.canvas.getBoundingClientRect();
        const cx = px - rect.left;
        const cy = py - rect.top;

        for (const [nid, pos] of Object.entries(this.nodePositions)) {
            const dx = cx - pos.x;
            const dy = cy - pos.y;
            if (Math.sqrt(dx * dx + dy * dy) < 14) {
                return nid;
            }
        }
        return null;
    }

    // ---- Internal ----

    _computeNodePositions() {
        for (const node of this.floorData.nodes) {
            this.nodePositions[node.node_id] = this._toPixel(node.x, node.y);
        }
    }

    _drawEdges() {
        const ctx = this.ctx;
        const edges = this.floorData.edges || [];

        // Draw normal edges first
        ctx.strokeStyle = '#CBD5E1';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        for (const [from, to, _w] of edges) {
            const p1 = this.nodePositions[from];
            const p2 = this.nodePositions[to];
            if (!p1 || !p2) continue;
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
        }
        ctx.stroke();
    }

    _drawNodes() {
        const ctx = this.ctx;
        for (const node of this.floorData.nodes) {
            const pos = this.nodePositions[node.node_id];
            if (!pos) continue;
            this._drawSingleNode(node, pos);
        }
    }

    _drawSingleNode(node, pos) {
        const ctx = this.ctx;
        const state = this.state[node.node_id] || 'normal';
        const isStart = state === 'start';
        const isGoal = state === 'goal';

        // Node body color by type
        const colors = {
            room: '#E5E7EB', corridor: '#D1D5DB', stair: '#DBEAFE',
            elevator: '#D1FAE5', entrance: '#FEE2E2', poi: '#FEF3C7',
        };
        const fillColor = colors[node.node_type] || '#E5E7EB';

        // Shape depends on type
        const r = 10;
        ctx.save();
        ctx.translate(pos.x, pos.y);

        if (node.node_type === 'corridor') {
            // Small dot for corridor segments
            ctx.fillStyle = fillColor;
            ctx.beginPath();
            ctx.arc(0, 0, 4, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = '#94A3B8';
            ctx.lineWidth = 1;
            ctx.stroke();
        } else if (node.node_type === 'stair') {
            // Diamond for stairs
            ctx.fillStyle = fillColor;
            ctx.beginPath();
            ctx.moveTo(0, -r);
            ctx.lineTo(r, 0);
            ctx.lineTo(0, r);
            ctx.lineTo(-r, 0);
            ctx.closePath();
            ctx.fill();
            ctx.strokeStyle = '#3B82F6';
            ctx.lineWidth = 1.5;
            ctx.stroke();
        } else if (node.node_type === 'elevator') {
            // Square for elevator
            ctx.fillStyle = fillColor;
            ctx.fillRect(-r, -r, r * 2, r * 2);
            ctx.strokeStyle = '#10B981';
            ctx.lineWidth = 1.5;
            ctx.strokeRect(-r, -r, r * 2, r * 2);
        } else if (node.node_type === 'poi') {
            // Circle with star
            ctx.fillStyle = fillColor;
            ctx.beginPath();
            ctx.arc(0, 0, r, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = '#F59E0B';
            ctx.lineWidth = 1.5;
            ctx.stroke();
        } else {
            // Rounded rect for rooms/entrances
            const w = r * 2.2;
            const h = r * 1.6;
            ctx.fillStyle = fillColor;
            this._roundRect(ctx, -w / 2, -h / 2, w, h, 3);
            ctx.fill();
            ctx.strokeStyle = '#94A3B8';
            ctx.lineWidth = 1.2;
            this._roundRect(ctx, -w / 2, -h / 2, w, h, 3);
            ctx.stroke();
        }

        // Start/Goal markers
        if (isStart || isGoal) {
            ctx.beginPath();
            ctx.arc(0, 0, r + 4, 0, Math.PI * 2);
            ctx.strokeStyle = isStart ? '#10B981' : '#EF4444';
            ctx.lineWidth = 2.5;
            ctx.stroke();
        }

        // Label
        const label = node.name.length > 12
            ? node.name.slice(0, 10) + '…' : node.name;
        ctx.fillStyle = '#374151';
        ctx.font = '9px -apple-system, "Microsoft YaHei", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(label, 0, r + 13);

        ctx.restore();
    }

    _drawPathHighlight() {
        if (this.highlightPath.length < 2) return;
        const ctx = this.ctx;
        ctx.strokeStyle = '#3B82F6';
        ctx.lineWidth = 3;
        ctx.lineCap = 'round';
        ctx.beginPath();
        for (let i = 0; i < this.highlightPath.length; i++) {
            const pos = this.nodePositions[this.highlightPath[i]];
            if (!pos) continue;
            if (i === 0) ctx.moveTo(pos.x, pos.y);
            else ctx.lineTo(pos.x, pos.y);
        }
        ctx.stroke();
    }

    _drawStateOverlay() {
        const ctx = this.ctx;
        for (const [nid, state] of Object.entries(this.state)) {
            if (['start', 'goal', 'normal', ''].includes(state)) continue;
            const pos = this.nodePositions[nid];
            if (!pos) continue;

            if (state === 'visited') {
                ctx.fillStyle = 'rgba(147, 197, 253, 0.4)';
                ctx.beginPath();
                ctx.arc(pos.x, pos.y, 8, 0, Math.PI * 2);
                ctx.fill();
            } else if (state === 'frontier') {
                ctx.strokeStyle = '#FBBF24';
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.arc(pos.x, pos.y, 9, 0, Math.PI * 2);
                ctx.stroke();
            } else if (state === 'current') {
                ctx.fillStyle = 'rgba(245, 158, 11, 0.6)';
                ctx.beginPath();
                ctx.arc(pos.x, pos.y, 10, 0, Math.PI * 2);
                ctx.fill();
            }
        }
    }

    _roundRect(ctx, x, y, w, h, r) {
        ctx.beginPath();
        ctx.moveTo(x + r, y);
        ctx.lineTo(x + w - r, y);
        ctx.arcTo(x + w, y, x + w, y + r, r);
        ctx.lineTo(x + w, y + h - r);
        ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
        ctx.lineTo(x + r, y + h);
        ctx.arcTo(x, y + h, x, y + h - r, r);
        ctx.lineTo(x, y + r);
        ctx.arcTo(x, y, x + r, y, r);
        ctx.closePath();
    }
}
