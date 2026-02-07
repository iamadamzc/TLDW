// TL;DW Frontend JavaScript - v3 Clean

class TLDWApp {
    constructor() {
        this.init();
    }

    init() {
        this.bindEvents();
        this.updateSummarizeButtonState();
    }

    bindEvents() {
        // Playlist selection
        const playlistSelect = document.getElementById('playlist-select');
        if (playlistSelect) {
            playlistSelect.addEventListener('change', (e) => {
                this.handlePlaylistChange(e.target.value);
            });
        }

        // Video checkbox selection
        document.addEventListener('change', (e) => {
            if (e.target.classList.contains('video-checkbox')) {
                this.updateSummarizeButtonState();
                this.updateSelectAllState();
            }
        });

        // Select all checkbox
        const selectAllCheckbox = document.getElementById('select-all');
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', (e) => {
                this.handleSelectAll(e.target.checked);
            });
        }

        // Summarize button
        const summarizeBtn = document.getElementById('summarize-btn');
        if (summarizeBtn) {
            summarizeBtn.addEventListener('click', () => {
                this.handleSummarize();
            });
        }
    }

    // ================================================================
    // PLAYLIST / VIDEO SELECTION
    // ================================================================

    async handlePlaylistChange(playlistId) {
        if (!playlistId) {
            this.hideVideosSection();
            return;
        }

        try {
            this.showLoading();

            const response = await fetch('/api/select-playlist', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ playlist_id: playlistId })
            });

            const data = await response.json();

            if (response.ok) {
                this.displayVideos(data.videos);
                this.showVideosSection();
            } else {
                this.showAlert('error', data.error || 'Failed to load playlist videos');
            }
        } catch (error) {
            console.error('Error loading playlist:', error);
            this.showAlert('error', 'Network error. Please try again.');
        } finally {
            this.hideLoading();
        }
    }

    displayVideos(videos) {
        const videosList = document.getElementById('videos-list');
        if (!videosList || !videos.length) return;

        videosList.innerHTML = '';

        videos.forEach(video => {
            const videoCard = this.createVideoCard(video);
            videosList.appendChild(videoCard);
        });

        if (typeof feather !== 'undefined') {
            feather.replace();
        }
    }

    createVideoCard(video) {
        const col = document.createElement('div');
        col.className = 'col-md-6 col-lg-4';

        col.innerHTML = `
            <div class="video-card fade-in">
                <div class="form-check">
                    <input class="form-check-input video-checkbox" 
                           type="checkbox" 
                           value="${video.id}" 
                           id="video-${video.id}">
                    <label class="form-check-label w-100" for="video-${video.id}">
                        <div class="video-thumbnail">
                            <img src="${video.thumbnail}" alt="Thumbnail" class="img-fluid">
                            <div class="video-overlay">
                                <i data-feather="play" class="play-icon"></i>
                            </div>
                        </div>
                        <div class="video-info">
                            <h6 class="video-title">${this.escapeHtml(video.title)}</h6>
                            <small class="text-muted">${this.escapeHtml(video.channel_title)}</small>
                        </div>
                    </label>
                </div>
            </div>
        `;

        return col;
    }

    handleSelectAll(checked) {
        const videoCheckboxes = document.querySelectorAll('.video-checkbox');
        videoCheckboxes.forEach(checkbox => {
            checkbox.checked = checked;
        });
        this.updateSummarizeButtonState();
    }

    updateSelectAllState() {
        const selectAllCheckbox = document.getElementById('select-all');
        const videoCheckboxes = document.querySelectorAll('.video-checkbox');

        if (!selectAllCheckbox || !videoCheckboxes.length) return;

        const checkedCount = document.querySelectorAll('.video-checkbox:checked').length;
        const totalCount = videoCheckboxes.length;

        selectAllCheckbox.checked = checkedCount === totalCount;
        selectAllCheckbox.indeterminate = checkedCount > 0 && checkedCount < totalCount;
    }

    updateSummarizeButtonState() {
        const summarizeBtn = document.getElementById('summarize-btn');
        const checkedVideos = document.querySelectorAll('.video-checkbox:checked');

        if (summarizeBtn) {
            summarizeBtn.disabled = checkedVideos.length === 0;

            if (checkedVideos.length > 0) {
                summarizeBtn.innerHTML = `
                    <i data-feather="zap"></i> 
                    Summarize ${checkedVideos.length} Video${checkedVideos.length !== 1 ? 's' : ''} with TL;DW
                `;
            } else {
                summarizeBtn.innerHTML = `
                    <i data-feather="zap"></i> 
                    Summarize with TL;DW
                `;
            }

            if (typeof feather !== 'undefined') {
                feather.replace();
            }
        }
    }

    // ================================================================
    // SUMMARIZE - Clean fire-and-forget flow
    //
    // 1. Show spinner modal
    // 2. POST /api/summarize
    // 3. Hide modal
    // 4. Show success/error alert
    // 5. Done. Email is the completion notification.
    // ================================================================

    async handleSummarize() {
        const checkedVideos = document.querySelectorAll('.video-checkbox:checked');
        if (checkedVideos.length === 0) {
            this.showAlert('warning', 'Please select at least one video to summarize.');
            return;
        }

        const videoIds = Array.from(checkedVideos).map(cb => cb.value);
        const videoCount = videoIds.length;

        // Show brief spinner
        this.showModal(videoCount);

        try {
            const response = await fetch('/api/summarize', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ video_ids: videoIds })
            });

            // Always hide modal first
            this.hideModal();

            if (response.status === 202) {
                const data = await response.json();
                const msg = data.message || "Got it! We're working on your summary. You'll receive an email when it's ready.";
                this.showAlert('success', msg);
                this.clearVideoSelection();
            } else {
                let errorMsg = `Request failed (${response.status})`;
                try {
                    const data = await response.json();
                    errorMsg = data.error || errorMsg;
                } catch (e) { /* use default */ }
                this.showAlert('error', errorMsg);
            }

        } catch (error) {
            console.error('Summarize error:', error);
            this.hideModal();
            this.showAlert('error', 'Network error. Please check your connection and try again.');
        }
    }

    // ================================================================
    // MODAL - Single show/hide pair, bulletproof cleanup
    // ================================================================

    showModal(videoCount) {
        const modalEl = document.getElementById('loadingModal');
        if (!modalEl) return;

        const modalBody = modalEl.querySelector('.modal-body');
        if (modalBody) {
            modalBody.innerHTML = `
                <div class="text-center p-4">
                    <div class="spinner-border text-primary mb-3" role="status">
                        <span class="visually-hidden">Submitting...</span>
                    </div>
                    <h5>Submitting Your Job</h5>
                    <p class="text-muted mb-0">Sending ${videoCount} video${videoCount !== 1 ? 's' : ''} for processing...</p>
                    <small class="text-muted">This should only take a moment</small>
                    <div class="mt-3">
                        <button type="button" class="btn btn-sm btn-outline-secondary" id="modal-cancel-btn">Cancel</button>
                    </div>
                </div>
            `;
        }

        let bsModal = bootstrap.Modal.getInstance(modalEl);
        if (!bsModal) {
            bsModal = new bootstrap.Modal(modalEl, { backdrop: 'static', keyboard: false });
        }
        bsModal.show();

        // Wire cancel
        const cancelBtn = document.getElementById('modal-cancel-btn');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => this.hideModal());
        }

        // Safety timeout
        clearTimeout(this._modalTimeout);
        this._modalTimeout = setTimeout(() => {
            console.warn('Modal auto-dismissed after 30s safety timeout');
            this.hideModal();
        }, 30000);
    }

    hideModal() {
        clearTimeout(this._modalTimeout);

        const modalEl = document.getElementById('loadingModal');
        if (modalEl) {
            const bsModal = bootstrap.Modal.getInstance(modalEl);
            if (bsModal) {
                try { bsModal.hide(); } catch (e) { /* ignore */ }
                try { bsModal.dispose(); } catch (e) { /* ignore */ }
            }
            modalEl.classList.remove('show');
            modalEl.style.display = 'none';
            modalEl.setAttribute('aria-hidden', 'true');
        }

        // Nuclear cleanup
        document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
        document.body.classList.remove('modal-open');
        document.body.style.removeProperty('overflow');
        document.body.style.removeProperty('padding-right');
    }

    // ================================================================
    // UI HELPERS
    // ================================================================

    clearVideoSelection() {
        document.querySelectorAll('.video-checkbox').forEach(cb => { cb.checked = false; });
        const selectAll = document.getElementById('select-all');
        if (selectAll) {
            selectAll.checked = false;
            selectAll.indeterminate = false;
        }
        this.updateSummarizeButtonState();
    }

    showVideosSection() {
        const el = document.getElementById('videos-section');
        if (el) {
            el.style.display = 'block';
            el.classList.add('slide-up');
        }
    }

    hideVideosSection() {
        const el = document.getElementById('videos-section');
        if (el) { el.style.display = 'none'; }
    }

    showLoading() {
        const el = document.getElementById('playlist-select');
        if (el) { el.disabled = true; }
    }

    hideLoading() {
        const el = document.getElementById('playlist-select');
        if (el) { el.disabled = false; }
    }

    showAlert(type, message) {
        const container = document.getElementById('alert-container');
        if (!container) return;

        const alertId = 'alert-' + Date.now();
        const alertClass = {
            'success': 'alert-success',
            'error': 'alert-danger',
            'warning': 'alert-warning',
            'info': 'alert-info'
        }[type] || 'alert-info';

        container.insertAdjacentHTML('beforeend', `
            <div class="alert ${alertClass} alert-dismissible fade show" role="alert" id="${alertId}">
                <strong>${type.charAt(0).toUpperCase() + type.slice(1)}:</strong> ${this.escapeHtml(message)}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        `);

        // Auto-dismiss success/info after 15 seconds
        if (type === 'success' || type === 'info') {
            setTimeout(() => {
                const el = document.getElementById(alertId);
                if (el) {
                    try { new bootstrap.Alert(el).close(); }
                    catch (e) { el.remove(); }
                }
            }, 15000);
        }
    }

    escapeHtml(text) {
        const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
        return text.replace(/[&<>"']/g, m => map[m]);
    }
}

// ================================================================
// INITIALIZATION
// ================================================================

let app;

document.addEventListener('DOMContentLoaded', () => {
    app = new TLDWApp();
    console.log('TLDWApp v3 initialized');
});

document.addEventListener('visibilitychange', () => {
    if (!document.hidden && window.location.pathname.includes('dashboard')) {
        console.log('Tab visible');
    }
});