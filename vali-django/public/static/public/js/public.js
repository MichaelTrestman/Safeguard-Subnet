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

    // Table pagination — any tbody[data-paginated] gets prev/next controls.
    document.querySelectorAll('tbody[data-paginated]').forEach(tbody => {
        const pageSize = parseInt(tbody.dataset.pageSize || '20', 10);
        const rows = Array.from(tbody.querySelectorAll('tr'));
        if (rows.length <= pageSize) return;  // no pagination needed

        let page = 0;
        const totalPages = Math.ceil(rows.length / pageSize);

        function render() {
            rows.forEach((r, i) => {
                r.style.display = (i >= page * pageSize && i < (page + 1) * pageSize) ? '' : 'none';
            });
            info.textContent = `Rows ${page * pageSize + 1}–${Math.min((page + 1) * pageSize, rows.length)} of ${rows.length}`;
            prev.disabled = page === 0;
            next.disabled = page === totalPages - 1;
        }

        const controls = document.createElement('div');
        controls.style.cssText = 'display:flex;align-items:center;gap:0.75rem;margin:0.5rem 0 1.5rem;font-size:0.8rem;color:#888;';

        const prev = document.createElement('button');
        prev.textContent = '← Prev';
        prev.style.cssText = 'background:none;border:1px solid #444;color:#aaa;padding:2px 10px;cursor:pointer;border-radius:3px;';
        prev.addEventListener('click', () => { page--; render(); });

        const next = document.createElement('button');
        next.textContent = 'Next →';
        next.style.cssText = 'background:none;border:1px solid #444;color:#aaa;padding:2px 10px;cursor:pointer;border-radius:3px;';
        next.addEventListener('click', () => { page++; render(); });

        const info = document.createElement('span');

        controls.append(prev, info, next);
        tbody.closest('.compare-wrap').insertAdjacentElement('afterend', controls);
        render();
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
