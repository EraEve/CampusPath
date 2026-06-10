/**
 * CampusPath — REST API Client
 *
 * Thin wrapper around fetch() for all 7 backend endpoints.
 * Every function returns {success, data, message} on success,
 * or throws an Error with a user-friendly message on failure.
 */

const API_BASE = 'http://localhost:5001/api';

const API = {
    // ---- Helpers ----

    async _fetch(url, options = {}) {
        try {
            const res = await fetch(url, options);
            const json = await res.json();
            if (!json.success) {
                throw new Error(json.message || 'Unknown error');
            }
            return json.data;
        } catch (err) {
            if (err.message.includes('Failed to fetch')) {
                throw new Error('Cannot connect to server. Is Flask running?');
            }
            throw err;
        }
    },

    async _get(path) {
        return this._fetch(`${API_BASE}${path}`);
    },

    async _post(path, body) {
        return this._fetch(`${API_BASE}${path}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
    },

    // ---- Building ----

    /** Get building metadata */
    async getBuilding() {
        return this._get('/building');
    },

    /** Get floor layout for Canvas rendering */
    async getFloor(n) {
        return this._get(`/building/floor/${n}`);
    },

    /** Get all nodes for dropdowns */
    async getAllNodes() {
        return this._get('/building/all-nodes');
    },

    // ---- Pathfinding ----

    /** Find a single path */
    async findPath({ start, goal, algorithm = 'dijkstra', heuristic = 'euclidean', recordSteps = false }) {
        return this._post('/path', { start, goal, algorithm, heuristic, record_steps: recordSteps });
    },

    /** Compare all algorithms on one pair */
    async compareAlgorithms(start, goal) {
        return this._post('/compare', { start, goal });
    },

    /** Batch compare on predefined scenarios */
    async batchCompare(sameFloor = false) {
        return this._post('/batch-compare', { same_floor: sameFloor });
    },

    /** Get algorithm steps for animation */
    async getAlgorithmSteps(algorithm, start, goal, heuristic = 'euclidean') {
        const params = new URLSearchParams({ start, goal, heuristic });
        return this._get(`/algorithm-steps/${algorithm}?${params}`);
    },

    // ---- Metadata ----

    /** Get available algorithms and heuristics */
    async getAlgorithmsMeta() {
        return this._get('/meta/algorithms');
    },
};
