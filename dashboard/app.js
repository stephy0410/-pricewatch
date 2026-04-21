const API_BASE = 'https://ameo7idb0b.execute-api.us-east-2.amazonaws.com/prod';

let allProducts = [];
let activeStore = 'all';
let activeStatus = 'all';
let activeSort = 'name';
let chart = null;
let selectedId = null;

//Helpers 

function fmt(n) {
    return '$' + Number(n).toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function pct(current, initial) {
    if (!initial || initial === 0) return 0;
    return ((current - initial) / initial) * 100;
}

function storeClass(store) {
    if (!store) return 'badge-other';
    const s = store.toLowerCase();
    if (s.includes('amazon')) return 'badge-amazon';
    if (s.includes('mercado')) return 'badge-mercado';
    if (s.includes('books') || s.includes('buscalibre') || s.includes('farmacias') || s.includes('nike')) return 'badge-books';
    return 'badge-other';
}

function uid() {
    return 'prod-' + Date.now().toString(36);
}

function showToast(msg, type = '') {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.className = 'toast show ' + type;
    clearTimeout(t._timer);
    t._timer = setTimeout(() => t.classList.remove('show'), 3200);
}

// Metrics

function updateMetrics(products) {
    document.getElementById('m-total').textContent = products.length;

    const downs = products.filter(p => Number(p.currentPrice) < Number(p.initialPrice));
    const ups = products.filter(p => Number(p.currentPrice) > Number(p.initialPrice));
    document.getElementById('m-down').textContent = downs.length;
    document.getElementById('m-up').textContent = ups.length;

    if (downs.length) {
        const best = downs.reduce((a, b) =>
            pct(Number(a.currentPrice), Number(a.initialPrice)) < pct(Number(b.currentPrice), Number(b.initialPrice)) ? a : b
        );
        const p = pct(Number(best.currentPrice), Number(best.initialPrice));
        document.getElementById('m-best').textContent = p.toFixed(1) + '%';
        document.getElementById('m-best-name').textContent = best.name;
    } else {
        document.getElementById('m-best').textContent = '—';
        document.getElementById('m-best-name').textContent = 'sin descuentos activos';
    }
}

// ── Store filter chips ────────────────────────────────────

function buildStoreFilters(products) {
    const stores = ['all', ...new Set(products.map(p => p.store).filter(Boolean))];
    const container = document.getElementById('store-filters');
    container.innerHTML = stores.map(s => `
    <button class="filter-chip ${s === activeStore ? 'active' : ''}" data-store="${s}">
      ${s === 'all' ? 'Todas' : s}
    </button>
  `).join('');
    container.querySelectorAll('.filter-chip').forEach(btn => {
        btn.addEventListener('click', () => {
            activeStore = btn.dataset.store;
            renderProducts();
            container.querySelectorAll('.filter-chip').forEach(b => b.classList.toggle('active', b.dataset.store === activeStore));
        });
    });
}

// Product card 

function productCard(p) {
    const curr = Number(p.currentPrice);
    const init = Number(p.initialPrice);
    const thr = Number(p.alertThreshold) || 5;
    const diff = pct(curr, init);
    const diffA = Math.abs(diff);
    const isDown = diff < -0.01;
    const isUp = diff > 0.01;
    const thPct = Math.min((diffA / thr) * 100, 100);
    const fillColor = diffA >= thr ? '#E24B4A' : '#378ADD';

    const badgeClass = isDown ? 'badge-down' : isUp ? 'badge-up' : 'badge-neutral';
    const badgeText = isDown ? `▼ ${diffA.toFixed(1)}%` : isUp ? `▲ ${diffA.toFixed(1)}%` : 'sin cambio';

    const imgHTML = p.image
        ? `<img class="product-img" src="${p.image}" alt="${p.name}" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'" /><div class="product-img-placeholder" style="display:none">🛍</div>`
        : `<div class="product-img-placeholder">🛍</div>`;

    return `
    <div class="product-card ${selectedId === p.productId ? 'selected' : ''}"
         data-id="${p.productId}" data-url="${p.url || ''}" onclick="onCardClick(this)">
      <div class="product-img-wrap">${imgHTML}</div>
      <div class="product-body">
        <div class="product-top">
          <div class="product-name">${p.name}</div>
          <span class="store-badge ${storeClass(p.store)}">${p.store || 'Tienda'}</span>
        </div>
        <div class="product-price-row">
          <span class="current-price">${fmt(curr)}</span>
          ${Math.abs(diff) > 0.01 ? `<span class="initial-price">${fmt(init)}</span>` : ''}
          <span class="change-badge ${badgeClass}">${badgeText}</span>
        </div>
        <div class="threshold-wrap">
          <div class="threshold-meta">
            <span>variación vs umbral</span>
            <span>${diffA.toFixed(1)}% / ${thr}%</span>
          </div>
          <div class="threshold-bar">
            <div class="threshold-fill" style="width:${thPct}%;background:${fillColor}"></div>
          </div>
        </div>
      </div>
      <div class="product-footer">
        <div style="display: flex; gap: 4px; align-items: center;">
          <button class="delete-btn" title="Eliminar producto" onclick="event.stopPropagation(); deleteProduct('${p.productId}', '${p.name.replace(/'/g, "\\'")}')">✕</button>
          <button class="edit-btn" onclick="event.stopPropagation(); openEditModal(${JSON.stringify(p).replace(/"/g, '&quot;')})">✎ Editar</button>
        </div>
        ${p.url ? `<a class="buy-link" href="${p.url}" target="_blank" onclick="event.stopPropagation()">Ir a comprar →</a>` : ''}
      </div>
    </div>
  `;
}

// Render products
function renderProducts() {
    let list = [...allProducts];

    if (activeStore !== 'all') list = list.filter(p => p.store === activeStore);

    if (activeStatus === 'down') list = list.filter(p => pct(Number(p.currentPrice), Number(p.initialPrice)) < -0.01);
    else if (activeStatus === 'up') list = list.filter(p => pct(Number(p.currentPrice), Number(p.initialPrice)) > 0.01);
    else if (activeStatus === 'same') list = list.filter(p => Math.abs(pct(Number(p.currentPrice), Number(p.initialPrice))) <= 0.01);

    if (activeSort === 'price-asc') list.sort((a, b) => Number(a.currentPrice) - Number(b.currentPrice));
    else if (activeSort === 'price-desc') list.sort((a, b) => Number(b.currentPrice) - Number(a.currentPrice));
    else if (activeSort === 'change-desc') list.sort((a, b) => Math.abs(pct(Number(b.currentPrice), Number(b.initialPrice))) - Math.abs(pct(Number(a.currentPrice), Number(a.initialPrice))));
    else list.sort((a, b) => a.name.localeCompare(b.name));

    const grid = document.getElementById('products-grid');
    if (!list.length) {
        grid.innerHTML = '<div class="empty-state">No hay productos que coincidan con los filtros.</div>';
        return;
    }

    list.forEach(p => {
        const diff = pct(Number(p.currentPrice), Number(p.initialPrice));
        const thr = Number(p.alertThreshold) || 5;
        if (Math.abs(diff) >= thr && p.url) {
            sendNotification(p.name, Number(p.initialPrice), Number(p.currentPrice), diff, p.url);
        }
    });

    grid.innerHTML = list.map(productCard).join('');
}

// Card click → load history

async function onCardClick(card) {
    const id = card.dataset.id;
    const url = card.dataset.url;
    selectedId = id;
    document.querySelectorAll('.product-card').forEach(c => c.classList.toggle('selected', c.dataset.id === id));

    const name = card.querySelector('.product-name')?.textContent || id;
    document.getElementById('chart-title').textContent = name;
    document.getElementById('chart-subtitle').textContent = 'Cargando historial...';

    const buyLink = document.getElementById('chart-buy-link');
    if (url) { buyLink.href = url; buyLink.style.display = 'inline-flex'; }
    else { buyLink.style.display = 'none'; }

    try {
        const res = await fetch(`${API_BASE}/products/${id}/history`);
        const data = await res.json();

        if (!data.length) {
            document.getElementById('chart-subtitle').textContent = 'Sin historial disponible aún.';
            if (chart) { chart.destroy(); chart = null; }
            return;
        }

        const sorted = [...data].sort((a, b) => a.timestamp.localeCompare(b.timestamp));
        const labels = sorted.map(d => {
            const dt = new Date(d.timestamp);
            return dt.toLocaleDateString('es-MX', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
        });
        const prices = sorted.map(d => Number(d.price));
        const minP = Math.min(...prices);
        const maxP = Math.max(...prices);

        document.getElementById('chart-subtitle').textContent =
            `${sorted.length} registros · mín ${fmt(minP)} · máx ${fmt(maxP)} · último: ${labels[labels.length - 1]}`;

        if (chart) chart.destroy();
        const ctx = document.getElementById('price-chart').getContext('2d');
        chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    label: 'Precio',
                    data: prices,
                    borderColor: '#185FA5',
                    backgroundColor: 'rgba(55,138,221,0.08)',
                    borderWidth: 2.5,
                    pointRadius: 4,
                    pointBackgroundColor: '#185FA5',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    tension: 0.35,
                    fill: true,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: { label: ctx => fmt(ctx.parsed.y) }
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(0,0,0,0.04)' },
                        ticks: { font: { size: 11 }, maxTicksLimit: 9, color: '#888780' }
                    },
                    y: {
                        grid: { color: 'rgba(0,0,0,0.04)' },
                        ticks: {
                            font: { size: 11 },
                            color: '#888780',
                            callback: v => '$' + Number(v).toLocaleString('es-MX')
                        }
                    }
                }
            }
        });
    } catch {
        document.getElementById('chart-subtitle').textContent = 'Error cargando historial.';
    }
}

// Load products

async function loadProducts() {
    const grid = document.getElementById('products-grid');
    grid.innerHTML = '<div class="loading-state"><div class="spinner"></div><span>Cargando productos...</span></div>';
    try {
        const res = await fetch(`${API_BASE}/products`);
        allProducts = await res.json();
        updateMetrics(allProducts);
        buildStoreFilters(allProducts);
        renderProducts();
    } catch {
        grid.innerHTML = '<div class="empty-state">Error conectando con la API.</div>';
    }
}

// Check URL

async function checkUrl() {
    const url = document.getElementById('input-url').value.trim();
    const fb = document.getElementById('url-feedback');
    const prev = document.getElementById('product-preview');
    if (!url) { fb.textContent = 'Ingresa una URL válida.'; fb.className = 'url-feedback err'; return; }

    fb.textContent = 'Verificando URL y extrayendo precio...';
    fb.className = 'url-feedback';
    prev.style.display = 'none';
    document.getElementById('check-url-btn').disabled = true;

    try {
        const res = await fetch(`${API_BASE}/check-url`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });
        const data = await res.json();

        if (data.scrapeable) {
            fb.textContent = '✓ ' + data.message;
            fb.className = 'url-feedback ok';
            if (data.og_title) document.getElementById('input-name').value = data.og_title;
            if (data.store) document.getElementById('input-store').value = data.store;
            if (data.price) document.getElementById('input-price').value = data.price.toFixed(2);
            if (data.og_image) {
                document.getElementById('preview-img').src = data.og_image;
                document.getElementById('preview-title').textContent = data.og_title || url;
                document.getElementById('product-preview').style.display = 'flex';
            } else {
                document.getElementById('url-feedback').textContent += ' — No se encontró imagen, puedes agregar una URL manualmente.';
            }
        } else {
            fb.textContent = '⚠ ' + data.message;
            fb.className = 'url-feedback warn';
            if (data.store) document.getElementById('input-store').value = data.store;
        }
    } catch {
        fb.textContent = 'Error al verificar la URL.';
        fb.className = 'url-feedback err';
    } finally {
        document.getElementById('check-url-btn').disabled = false;
    }
}
// Save product

async function saveProduct() {
    const url = document.getElementById('input-url').value.trim();
    const name = document.getElementById('input-name').value.trim();
    const store = document.getElementById('input-store').value.trim();
    const price = parseFloat(document.getElementById('input-price').value);
    const threshold = parseFloat(document.getElementById('input-threshold').value) || 5;
    const image = document.getElementById('preview-img').src ||
        document.getElementById('input-image').value.trim() || '';

    if (!url || !name || !store || isNaN(price)) {
        showToast('Completa todos los campos requeridos.', 'error');
        return;
    }

    const btn = document.getElementById('save-product-btn');
    btn.disabled = true;
    btn.textContent = 'Guardando...';

    try {
        const res = await fetch(`${API_BASE}/products`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                productId: uid(),
                name, url, store,
                currentPrice: price,
                alertThreshold: threshold,
                image
            })
        });
        if (res.ok) {
            closeModal();
            showToast('Producto agregado correctamente.', 'success');
            await loadProducts();
        } else {
            const err = await res.json();
            showToast('Error: ' + (err.error || 'No se pudo guardar.'), 'error');
        }
    } catch {
        showToast('Error de conexión.', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Guardar producto';
    }
}

// Modal

function openModal() {
    document.getElementById('add-modal').style.display = 'flex';
    document.getElementById('input-url').value = '';
    document.getElementById('input-name').value = '';
    document.getElementById('input-store').value = '';
    document.getElementById('input-price').value = '';
    document.getElementById('input-threshold').value = '5';
    document.getElementById('url-feedback').textContent = '';
    document.getElementById('url-feedback').className = 'url-feedback';
    document.getElementById('product-preview').style.display = 'none';
    document.getElementById('input-image').value = '';
}

function closeModal() {
    document.getElementById('add-modal').style.display = 'none';
}

// Init
document.addEventListener('DOMContentLoaded', () => {
    loadProducts();

    document.getElementById('refresh-btn').addEventListener('click', loadProducts);
    document.getElementById('open-add-modal').addEventListener('click', openModal);
    document.getElementById('close-modal').addEventListener('click', closeModal);
    document.getElementById('cancel-modal').addEventListener('click', closeModal);
    document.getElementById('check-url-btn').addEventListener('click', checkUrl);
    document.getElementById('save-product-btn').addEventListener('click', saveProduct);
    document.getElementById('close-edit-modal').addEventListener('click', () => document.getElementById('edit-modal').style.display = 'none');
    document.getElementById('cancel-edit-modal').addEventListener('click', () => document.getElementById('edit-modal').style.display = 'none');
    document.getElementById('save-edit-btn').addEventListener('click', saveEdit);
    document.getElementById('input-image').addEventListener('input', e => {
        const url = e.target.value.trim();
        const img = document.getElementById('preview-img');
        const prev = document.getElementById('product-preview');
        if (url) {
            img.src = url;
            img.onerror = () => {
                prev.style.display = 'none';
                showToast('No se pudo cargar esa imagen.', 'error');
            };
            img.onload = () => { prev.style.display = 'flex'; };
        } else {
            prev.style.display = 'none';
        }
    });
    document.getElementById('sort-select').addEventListener('change', e => {
        activeSort = e.target.value;
        renderProducts();
    });

    document.getElementById('status-filter').addEventListener('change', e => {
        activeStatus = e.target.value;
        renderProducts();
    });

    document.getElementById('add-modal').addEventListener('click', e => {
        if (e.target === document.getElementById('add-modal')) closeModal();
    });
    requestNotificationPermission();
});
// Delete Product
async function deleteProduct(productId, name) {
    if (!confirm(`¿Eliminar "${name}"?`)) return;
    try {
        const res = await fetch(`${API_BASE}/products/${productId}`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' }
        });
        if (res.ok) {
            showToast('Producto eliminado.', 'success');
            await loadProducts();
        } else {
            showToast('Error al eliminar.', 'error');
        }
    } catch {
        showToast('Error de conexión.', 'error');
    }
}

// Edit Product

let editingProductId = null;

function openEditModal(p) {
    editingProductId = p.productId;
    document.getElementById('edit-name').value = p.name;
    document.getElementById('edit-threshold').value = p.alertThreshold;
    document.getElementById('edit-image').value = p.image || '';
    document.getElementById('edit-modal').style.display = 'flex';
}

async function saveEdit() {
    const name = document.getElementById('edit-name').value.trim();
    const threshold = parseFloat(document.getElementById('edit-threshold').value);
    const image = document.getElementById('edit-image').value.trim();
    if (!name || isNaN(threshold)) { showToast('Completa los campos.', 'error'); return; }

    try {
        const res = await fetch(`${API_BASE}/products/${editingProductId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, alertThreshold: threshold, image })
        });
        if (res.ok) {
            document.getElementById('edit-modal').style.display = 'none';
            showToast('Producto actualizado.', 'success');
            await loadProducts();
        } else {
            showToast('Error al actualizar.', 'error');
        }
    } catch {
        showToast('Error de conexión.', 'error');
    }
}

async function requestNotificationPermission() {
    if (!('Notification' in window)) return;
    if (Notification.permission === 'default') {
        await Notification.requestPermission();
    }
}

function sendNotification(productName, precioAnterior, precioNuevo, variacion, url) {
    if (Notification.permission !== 'granted') return;
    const isDown = variacion < 0;
    const emoji = isDown ? '📉' : '📈';
    const msg = isDown
        ? `Bajó ${Math.abs(variacion).toFixed(1)}% — ahora $${precioNuevo.toLocaleString('es-MX')}`
        : `Subió ${variacion.toFixed(1)}% — ahora $${precioNuevo.toLocaleString('es-MX')}`;

    const notif = new Notification(`${emoji} ${productName}`, {
        body: msg,
        icon: '/favicon.ico',
    });

    if (url) notif.onclick = () => window.open(url, '_blank');
}

if (Math.abs(diff) >= thr && p.url) {
    sendNotification(p.name, Number(p.initialPrice), Number(p.currentPrice), diff, p.url);
}