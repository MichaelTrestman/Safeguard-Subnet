// EU AI Act countdown timer — enforcement date: August 2, 2026
// Only runs on pages that have the countdown elements (landing page).
function updateCountdown() {
    const el = document.getElementById('countdown-days');
    if (!el) return;  // not on this page

    const target = new Date('2026-08-02T00:00:00Z');
    const now = new Date();
    const diff = target - now;

    if (diff <= 0) {
        const c = document.getElementById('countdown');
        if (c) c.textContent = 'ENFORCEMENT ACTIVE';
        return;
    }

    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((diff % (1000 * 60)) / 1000);

    el.textContent = days;
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

    // Model-page tab switching (Concerns | Behaviors).
    const tabBtns = document.querySelectorAll('.model-tab-btn');
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.dataset.tab;
            tabBtns.forEach(b => b.classList.toggle('active', b === btn));
            document.querySelectorAll('.model-tab-panel').forEach(panel => {
                panel.style.display = panel.id === 'tab-' + target ? '' : 'none';
            });
        });
    });

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
