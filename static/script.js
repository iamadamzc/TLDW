// TL;DW Frontend JavaScript

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

    async handlePlaylistChange(playlistId) {
        if (!playlistId) {
            this.hideVideosSection();
            return;
        }

        try {
            this.showLoading();
            
            const response = await fetch('/api/select-playlist', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
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

        // Reinitialize Feather icons
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
            
            // Reinitialize Feather icons
            if (typeof feather !== 'undefined') {
                feather.replace();
            }
        }
    }

    async handleSummarize(videoIds) {
        this.showLoadingModal();
        try {
            const res = await fetch('/api/summarize', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ video_ids: videoIds })
            });

            const ct = res.headers.get('content-type') || '';
            const body = await res.text();

            if (!res.ok) {
                this.hideLoadingModal();
                throw new Error(`${res.status} ${res.statusText}: ${body.slice(0, 200)}`);
            }

            const data = ct.includes('application/json') ? JSON.parse(body) : {};
            this.showToast(data.message || 'Request received — we’ll email you when it’s ready.');
            this.clearVideoSelection();
            this.hideLoadingModal();
        } catch (err) {
            console.error(err);
            this.showToast('Failed to start the job. Please try again.');
            this.hideLoadingModal();
        }
    }

    clearVideoSelection() {
        const videoCheckboxes = document.querySelectorAll('.video-checkbox');
        const selectAllCheckbox = document.getElementById('select-all');
        
        videoCheckboxes.forEach(checkbox => {
            checkbox.checked = false;
        });
        
        if (selectAllCheckbox) {
            selectAllCheckbox.checked = false;
            selectAllCheckbox.indeterminate = false;
        }
        
        this.updateSummarizeButtonState();
    }

    showVideosSection() {
        const videosSection = document.getElementById('videos-section');
        if (videosSection) {
            videosSection.style.display = 'block';
            videosSection.classList.add('slide-up');
        }
    }

    hideVideosSection() {
        const videosSection = document.getElementById('videos-section');
        if (videosSection) {
            videosSection.style.display = 'none';
        }
    }

    showLoadingModal() {
        const modal = new bootstrap.Modal(document.getElementById('loadingModal'));
        modal.show();
    }

    hideLoadingModal() {
        const modalElement = document.getElementById('loadingModal');
        const modal = bootstrap.Modal.getInstance(modalElement);
        if (modal) {
            modal.hide();
        }
    }

    showLoading() {
        // Add loading state to playlist select or other UI elements
        const playlistSelect = document.getElementById('playlist-select');
        if (playlistSelect) {
            playlistSelect.disabled = true;
        }
    }

    hideLoading() {
        const playlistSelect = document.getElementById('playlist-select');
        if (playlistSelect) {
            playlistSelect.disabled = false;
        }
    }

    showToast(message, type = 'info') {
        const toastContainer = document.getElementById('toast-container');
        if (!toastContainer) return;

        const toastId = 'toast-' + Date.now();
        const toastHtml = `
            <div class="toast" role="alert" aria-live="assertive" aria-atomic="true" id="${toastId}">
                <div class="toast-header">
                    <strong class="me-auto">${type.charAt(0).toUpperCase() + type.slice(1)}</strong>
                    <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
                <div class="toast-body">
                    ${this.escapeHtml(message)}
                </div>
            </div>
        `;

        toastContainer.insertAdjacentHTML('beforeend', toastHtml);
        const toastElement = document.getElementById(toastId);
        const toast = new bootstrap.Toast(toastElement);
        toast.show();
    }

    escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, m => map[m]);
    }
}

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new TLDWApp();
});

// Handle page visibility changes to refresh tokens if needed
document.addEventListener('visibilitychange', () => {
    if (!document.hidden && window.location.pathname.includes('dashboard')) {
        // Optionally refresh data when user returns to tab
        console.log('Tab became visible - could refresh data here');
    }
});
