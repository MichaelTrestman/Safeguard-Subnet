// EU AI Act countdown timer — enforcement date: August 2, 2026
function updateCountdown() {
    const target = new Date('2026-08-02T00:00:00Z');
    const now = new Date();
    const diff = target - now;

    if (diff <= 0) {
        document.getElementById('countdown').textContent = 'ENFORCEMENT ACTIVE';
        return;
    }

    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((diff % (1000 * 60)) / 1000);

    document.getElementById('countdown-days').textContent = days;
    document.getElementById('countdown-hours').textContent = String(hours).padStart(2, '0');
    document.getElementById('countdown-minutes').textContent = String(minutes).padStart(2, '0');
    document.getElementById('countdown-seconds').textContent = String(seconds).padStart(2, '0');
}

setInterval(updateCountdown, 1000);
updateCountdown();

// Scroll-triggered fade-in
const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('visible');
        }
    });
}, { threshold: 0.1 });

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.fade-in').forEach(el => observer.observe(el));

    // Fetch recent activity feed for the landing-page embed (Phase 2).
    const feedTarget = document.getElementById('activity-feed-embed');
    if (!feedTarget) return;

    fetch('/activity/feed.json')
        .then(r => r.ok ? r.json() : Promise.reject(r.status))
        .then(data => {
            if (!data.items || data.items.length === 0) {
                feedTarget.innerHTML = '<p class="activity-empty">No recent activity yet.</p>';
                return;
            }
            feedTarget.innerHTML = data.items.map(row => `
                <div class="activity-row">
                    <span class="activity-ts">${row.ts}</span>
                    <span class="activity-label">${row.label}</span>
                </div>
            `).join('');
        })
        .catch(() => {
            feedTarget.innerHTML = '<p class="activity-empty">Activity feed unavailable.</p>';
        });
});
