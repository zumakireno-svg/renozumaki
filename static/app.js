const STORAGE_KEY = 'tech_house_store_v1';
const SQLITE_IMPORT_KEY = 'tech_house_sqlite_import_done_v1';
const COLOR_MODE_KEY = 'tech_house_color_mode';
const DEFAULT_PRODUCTS = [
  {
    id: 'cam-01',
    name: 'كاميرا مراقبة 4K Pro',
    category: 'أمن',
    badge: 'مميز',
    price: 'LE 3,200',
    oldPrice: 'LE 4,100',
    description: 'كاميرا خارجية عالية الدقة مع رؤية ليلية قوية وتسجيل مستمر ومقاومة للماء.',
    specs: ['دقة 4K Ultra HD', 'رؤية ليلية حتى 30 متر', 'حماية IP66', 'تثبيت سهل وسريع'],
    images: [
      'https://images.unsplash.com/photo-1555618561-2e7a48b3c2c0?auto=format&fit=crop&w=1200&q=80',
      'https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80',
      'https://images.unsplash.com/photo-1581092921461-eab62e97a780?auto=format&fit=crop&w=1200&q=80'
    ]
  },
  {
    id: 'net-02',
    name: 'موجه شبكة SMB Pro',
    category: 'شبكات',
    badge: 'جديد',
    price: 'LE 2,600',
    oldPrice: 'LE 3,300',
    description: 'موجه شبكة احترافي يدعم أداء متوازن للمنزل والعمل مع تحكم سهل واتصال مستقر.',
    specs: ['سرعة حتى 1.2 Gbps', '4 منافذ LAN', 'حماية WPA3', 'واجهة سهلة الإدارة'],
    images: [
      'https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=1200&q=80',
      'https://images.unsplash.com/photo-1542744173-8e7e534b2089?auto=format&fit=crop&w=1200&q=80'
    ]
  },
  {
    id: 'dev-03',
    name: 'لوحة تحكم ذكية Home Hub',
    category: 'أجهزة',
    badge: 'متميز',
    price: 'LE 1,900',
    oldPrice: 'LE 2,300',
    description: 'لوحة تحكم مركزية لإدارة الأجهزة الذكية في المنزل أو المكتب بسهولة عالية.',
    specs: ['دعم Zigbee + WiFi', 'تحكم صوتي', 'إدارة أوتوماتيك', 'واجهة عربية'],
    images: [
      'https://images.unsplash.com/photo-1516321497487-e288fb19713f?auto=format&fit=crop&w=1200&q=80',
      'https://images.unsplash.com/photo-1498050108023-c5249f4df085?auto=format&fit=crop&w=1200&q=80'
    ]
  },
  {
    id: 'svc-04',
    name: 'خدمة تركيب وصيانة الأنظمة',
    category: 'خدمات',
    badge: 'استشارة مجانية',
    price: 'تواصل للاستشارة',
    oldPrice: '',
    description: 'خدمة تركيب شبكات وأنظمة أمنية مع مراجعة فنية، ضبط إعدادات، وتوجيه فني حسب الموقع.',
    specs: ['دراسة الموقع', 'تركيب احترافي', 'ضبط وإعداد', 'دعم فني مستمر'],
    images: [
      'https://images.unsplash.com/photo-1522202176988-66273c2fd55f?auto=format&fit=crop&w=1200&q=80',
      'https://images.unsplash.com/photo-1552664730-d307ca884978?auto=format&fit=crop&w=1200&q=80'
    ]
  },
  {
    id: 'cam-05',
    name: 'نظام كاميرات تجاري',
    category: 'أمن',
    badge: 'أفضل اختيار',
    price: 'LE 5,400',
    oldPrice: 'LE 6,500',
    description: 'حل كامل للمؤسسات والورش مع ربط متعدد، مراقبة مباشرة، ونسخ احتياطي ذكي.',
    specs: ['8 كاميرات متوافقة', 'تخزين موسع', 'مراقبة عبر الهاتف', 'تسجيل 24/7'],
    images: [
      'https://images.unsplash.com/photo-1581092160607-ee2279d0f0d7?auto=format&fit=crop&w=1200&q=80',
      'https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=1200&q=80'
    ]
  }
];

const DEFAULT_USERS = [];

function getState() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    const initial = { products: DEFAULT_PRODUCTS, users: DEFAULT_USERS, session: null };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(initial));
    return initial;
  }

  try {
    const parsed = JSON.parse(raw);
    if (!parsed.products) {
      const refreshed = { products: DEFAULT_PRODUCTS, users: DEFAULT_USERS, session: null };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(refreshed));
      return refreshed;
    }
    const sanitized = { ...parsed, users: DEFAULT_USERS, session: null };
    persistState(sanitized);
    return sanitized;
  } catch (error) {
    const refreshed = { products: DEFAULT_PRODUCTS, users: DEFAULT_USERS, session: null };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(refreshed));
    return refreshed;
  }
}

function persistState(nextState) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(nextState));
}

const state = getState();
const browserProductsBeforeSqlite = [...state.products];

async function syncProductsWithServer() {
  const response = await fetch('/api/products');
  if (!response.ok) throw new Error('تعذر تحميل المنتجات من الخادم');

  const catalog = await response.json();
  if (!localStorage.getItem(SQLITE_IMPORT_KEY) && getCurrentUser()) {
    const productsById = new Map(catalog.products.map((product) => [String(product.id), product]));
    browserProductsBeforeSqlite.forEach((product) => {
      if (!productsById.has(String(product.id))) {
        productsById.set(String(product.id), product);
      }
    });
    state.products = Array.from(productsById.values());
    await saveProductsToServer();
    localStorage.setItem(SQLITE_IMPORT_KEY, 'true');
    return;
  }

  state.products = catalog.products;
  if (localStorage.getItem(SQLITE_IMPORT_KEY)) {
    persistState(state);
  }
}

async function saveProductsToServer() {
  const csrf = await fetch('/api/admin/csrf').then((r) => r.json());
  const response = await fetch('/api/products', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf.csrf_token },
    body: JSON.stringify({ products: state.products })
  });
  if (!response.ok) throw new Error('تعذر حفظ المنتجات على الخادم');

  const catalog = await response.json();
  state.products = catalog.products;
  persistState(state);
}

async function validateAdminSession() {
  const response = await fetch('/api/admin/session');
  if (!response.ok) throw new Error('تعذر التحقق من جلسة الإدارة');

  const result = await response.json();
  if (!result.authenticated) {
    setCurrentUser(null);
    return;
  }

  if (!getCurrentUser() || getCurrentUser().username !== result.username) {
    setCurrentUser({ username: result.username, name: result.username, role: 'super_admin', permissions: ['view', 'add', 'edit', 'delete'] });
  }
}

function WhatsAppLink(productName) {
  const text = encodeURIComponent(`السلام عليكم، أريد الاستفسار عن طلب منتج: ${productName}`);
  return `https://wa.me/201111600231?text=${text}`;
}

function productPageUrl(productId) {
  const base = new URL(window.location.origin);
  base.pathname = `/product/${encodeURIComponent(productId)}`;
  return base.toString();
}

function productShareUrl(productId) {
  return productPageUrl(productId);
}

async function shareProduct(productId) {
  const product = state.products.find((item) => item.id === productId);
  if (!product) return;

  const url = productShareUrl(product.id);
  if (navigator.share) {
    try {
      await navigator.share({ title: product.name, text: product.description, url });
      return;
    } catch (error) {
      if (error.name === 'AbortError') return;
    }
  }

  try {
    await navigator.clipboard.writeText(url);
    window.alert('تم نسخ رابط المنتج للمشاركة.');
  } catch (error) {
    window.prompt('انسخ رابط المنتج:', url);
  }
}

function ensureMetaTag(tagName, attributes) {
  let tag = document.querySelector(`meta[${tagName}]`);
  if (!tag) {
    tag = document.createElement('meta');
    document.head.appendChild(tag);
  }
  Object.entries(attributes).forEach(([key, value]) => {
    tag.setAttribute(key, value);
  });
  return tag;
}

function updateProductMeta(product) {
  const fallbackTitle = 'بيت التكنولوجيا | Tech House';
  const fallbackDescription = 'معرض تقني احترافي لمنتجات وخدمات تقنية ومراقبة وأنظمة ذكية.';
  const productTitle = product ? `${product.name} | بيت التكنولوجيا` : fallbackTitle;
  const productDescription = product ? product.description : fallbackDescription;
  const productImage = product && product.images && product.images[0] ? product.images[0] : 'https://images.unsplash.com/photo-1552664730-d307ca884978?auto=format&fit=crop&w=1200&q=80';

  document.title = productTitle;
  ensureMetaTag('name="description"', { name: 'description', content: productDescription });
  ensureMetaTag('property="og:title"', { property: 'og:title', content: productTitle });
  ensureMetaTag('property="og:description"', { property: 'og:description', content: productDescription });
  ensureMetaTag('property="og:image"', { property: 'og:image', content: productImage });
  ensureMetaTag('property="og:type"', { property: 'og:type', content: 'website' });
  ensureMetaTag('property="og:url"', { property: 'og:url', content: window.location.href });
  ensureMetaTag('name="twitter:card"', { name: 'twitter:card', content: 'summary_large_image' });
  ensureMetaTag('name="twitter:title"', { name: 'twitter:title', content: productTitle });
  ensureMetaTag('name="twitter:description"', { name: 'twitter:description', content: productDescription });
  ensureMetaTag('name="twitter:image"', { name: 'twitter:image', content: productImage });
}

function escapeHtml(value = '') {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function checkIconMarkup() {
  return '<svg class="h-4 w-4 shrink-0 text-emerald-600" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m5 12 4 4L19 6"/></svg>';
}

let motionObserver;

function observeMotionTargets(root = document) {
  root.querySelectorAll('[data-motion="reveal"]:not([data-motion-observed])').forEach((target, index) => {
    target.dataset.motionObserved = 'true';
    target.style.setProperty('--motion-delay', `${Math.min(index, 5) * 110}ms`);
    if (motionObserver) {
      target.classList.add('motion-pending');
      motionObserver.observe(target);
    } else {
      target.classList.add('motion-visible');
    }
  });
}

function initializeMotion() {
  initializeScrollProgress();
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    observeMotionTargets();
    return;
  }

  if ('IntersectionObserver' in window) {
    motionObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.remove('motion-pending');
          entry.target.classList.add('motion-visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.14, rootMargin: '0px 0px -36px 0px' });
    document.documentElement.classList.add('motion-enabled');
  }

  observeMotionTargets();
  initializePointerMotion();
}

function applyPointerTilt(element, event, strength) {
  const bounds = element.getBoundingClientRect();
  const horizontal = (event.clientX - bounds.left) / bounds.width - 0.5;
  const vertical = (event.clientY - bounds.top) / bounds.height - 0.5;
  element.style.setProperty('--tilt-x', `${-vertical * strength}deg`);
  element.style.setProperty('--tilt-y', `${horizontal * strength}deg`);
  element.style.setProperty('--pointer-x', `${(horizontal + 0.5) * 100}%`);
  element.style.setProperty('--pointer-y', `${(vertical + 0.5) * 100}%`);
  element.style.setProperty('--pointer-opacity', '1');
}

function resetPointerTilt(element) {
  element.style.removeProperty('--tilt-x');
  element.style.removeProperty('--tilt-y');
  element.style.removeProperty('--pointer-opacity');
}

function initializePointerMotion() {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches || window.matchMedia('(hover: none)').matches) return;

  document.querySelectorAll('[data-tilt-card]').forEach((element) => {
    element.addEventListener('pointermove', (event) => applyPointerTilt(element, event, 4));
    element.addEventListener('pointerleave', () => resetPointerTilt(element));
  });

  const grid = document.getElementById('productGrid');
  if (!grid || grid.dataset.tiltReady) return;
  grid.dataset.tiltReady = 'true';

  let activeCard = null;
  grid.addEventListener('pointermove', (event) => {
    const card = event.target.closest('.product-motion-card');
    if (activeCard && activeCard !== card) resetPointerTilt(activeCard);
    activeCard = card;
    if (card) applyPointerTilt(card, event, 3.5);
  });
  grid.addEventListener('pointerout', (event) => {
    const card = event.target.closest('.product-motion-card');
    if (card && !card.contains(event.relatedTarget)) {
      resetPointerTilt(card);
      if (activeCard === card) activeCard = null;
    }
  });
}

function initializeScrollProgress() {
  const progress = document.getElementById('scrollProgress');
  if (!progress) return;

  let frame = null;
  const updateProgress = () => {
    const scrollableHeight = document.documentElement.scrollHeight - window.innerHeight;
    const progressValue = scrollableHeight > 0 ? window.scrollY / scrollableHeight : 0;
    progress.style.transform = `scaleX(${Math.min(1, Math.max(0, progressValue))})`;
    frame = null;
  };

  window.addEventListener('scroll', () => {
    if (frame === null) frame = window.requestAnimationFrame(updateProgress);
  }, { passive: true });
  updateProgress();
}

function renderProducts() {
  const grid = document.getElementById('productGrid');
  const countEl = document.getElementById('productCount');
  const searchValue = document.getElementById('productSearch')?.value?.trim().toLowerCase() || '';
  const activeFilter = document.querySelector('.filter-btn.active')?.dataset.filter || 'الكل';

  if (!grid) return;

  const currentProducts = state.products.filter((product) => {
    const matchesCategory = activeFilter === 'الكل' || product.category === activeFilter;
    const haystack = `${product.name} ${product.category} ${product.description}`.toLowerCase();
    const matchesSearch = !searchValue || haystack.includes(searchValue);
    return matchesCategory && matchesSearch;
  });

  grid.innerHTML = currentProducts.map((product, index) => `
    <article class="product-card-enter product-motion-card group overflow-hidden rounded-[1.75rem] border border-slate-200 bg-white shadow-sm transition hover:shadow-xl" style="--motion-delay: ${Math.min(index, 8) * 95}ms">
      <div class="relative overflow-hidden">
        <img src="${product.images[0]}" alt="${escapeHtml(product.name)}" loading="lazy" decoding="async" class="h-64 w-full object-cover transition duration-500 group-hover:scale-105" />
        <span class="absolute right-4 top-4 rounded-full bg-white/90 px-3 py-1 text-[10px] font-black tracking-[0.18em] text-tech-600">${escapeHtml(product.badge || 'منتج')}</span>
      </div>
      <div class="p-5">
        <div class="text-[10px] font-black tracking-[0.18em] text-tech-600">${escapeHtml(product.category)}</div>
        <h3 class="mt-3 text-xl font-black text-slate-900">${escapeHtml(product.name)}</h3>
        <p class="mt-3 text-sm leading-7 text-slate-600">${escapeHtml(product.description)}</p>

        <div class="mt-5 flex items-end justify-between gap-3">
          <div>
            <div class="text-[10px] font-black tracking-[0.18em] text-slate-400">السعر</div>
            <div class="mt-1 text-xl font-black text-slate-900">${escapeHtml(product.price)}</div>
            ${product.oldPrice ? `<div class="text-xs text-slate-400 line-through">${escapeHtml(product.oldPrice)}</div>` : ''}
          </div>
          <div class="flex flex-col gap-2">
            <button type="button" class="product-preview-btn rounded-full bg-tech-500 px-3 py-2 text-[11px] font-black text-white" data-id="${product.id}">عرض التفاصيل</button>
            <a href="${productShareUrl(product.id)}" class="product-share-link rounded-full bg-slate-100 px-3 py-2 text-center text-[11px] font-black text-slate-700">مشاركة</a>
            <a href="${WhatsAppLink(product.name)}" target="_blank" rel="noreferrer" class="rounded-full bg-emerald-500 px-3 py-2 text-center text-[11px] font-black text-white">طلب سريع</a>
          </div>
        </div>
      </div>
    </article>
  `).join('');

  countEl.textContent = currentProducts.length;

  document.querySelectorAll('.product-preview-btn').forEach((button) => {
    button.addEventListener('click', () => {
      window.location.href = productPageUrl(button.dataset.id);
    });
  });

  document.querySelectorAll('.product-share-link').forEach((link) => {
    link.addEventListener('click', (event) => {
      event.preventDefault();
      const productId = link.dataset.id || link.getAttribute('href')?.split('/').filter(Boolean).pop();
      if (!productId) return;
      shareProduct(productId);
    });
  });
}

function openProductModal(productId) {
  const product = state.products.find((item) => item.id === productId);
  if (!product) return;

  const modal = document.getElementById('productModal');
  const mainImage = document.getElementById('modalMainImage');
  const thumbs = document.getElementById('modalThumbs');
  const badge = document.getElementById('modalBadge');
  const title = document.getElementById('modalTitle');
  const price = document.getElementById('modalPrice');
  const oldPrice = document.getElementById('modalOldPrice');
  const description = document.getElementById('modalDescription');
  const specs = document.getElementById('modalSpecs');
  const buyButton = document.getElementById('modalBuyButton');

  if (!modal || !mainImage || !thumbs || !badge || !title || !price || !description || !specs || !buyButton) return;

  mainImage.src = product.images[0];
  mainImage.alt = product.name;
  mainImage.loading = 'eager';
  mainImage.decoding = 'async';
  badge.textContent = product.badge || 'منتج';
  title.textContent = product.name;
  price.textContent = product.price;
  oldPrice.textContent = product.oldPrice || '';
  oldPrice.classList.toggle('hidden', !product.oldPrice);
  description.textContent = product.description;
  specs.innerHTML = (product.specs || []).map((item) => `<li class="flex items-center gap-2">${checkIconMarkup()}${escapeHtml(item)}</li>`).join('');
  buyButton.href = WhatsAppLink(product.name);
  updateProductMeta(product);
  const productUrl = productShareUrl(product.id);
  window.history.replaceState({}, '', productUrl);

  thumbs.innerHTML = product.images.map((image, index) => `
    <button type="button" class="thumb-btn rounded-xl border ${index === 0 ? 'border-tech-500 bg-white' : 'border-slate-200 bg-white'} p-1 transition hover:border-tech-500" data-image="${image}">
      <img src="${image}" alt="${escapeHtml(product.name)}" loading="lazy" decoding="async" class="h-20 w-full rounded-lg object-cover" />
    </button>
  `).join('');

  thumbs.querySelectorAll('.thumb-btn').forEach((button) => {
    button.addEventListener('click', () => {
      mainImage.src = button.dataset.image;
      thumbs.querySelectorAll('.thumb-btn').forEach((thumb) => thumb.classList.remove('border-tech-500'));
      button.classList.add('border-tech-500');
    });
  });

  modal.classList.remove('hidden');
  document.body.classList.add('overflow-hidden');
}

function closeProductModal() {
  const modal = document.getElementById('productModal');
  if (modal) {
    modal.classList.add('hidden');
    document.body.classList.remove('overflow-hidden');
  }

  const url = new URL(window.location.href);
  if (url.searchParams.has('product')) {
    url.searchParams.delete('product');
    url.hash = '';
    window.history.replaceState({}, '', url.toString());
  }
  updateProductMeta(null);
}

function initializeFilters() {
  const searchInput = document.getElementById('productSearch');
  const filterButtons = document.querySelectorAll('.filter-btn');

  searchInput?.addEventListener('input', renderProducts);

  filterButtons.forEach((button) => {
    button.addEventListener('click', () => {
      filterButtons.forEach((btn) => {
        btn.classList.remove('active');
        btn.classList.remove('bg-tech-500', 'text-white');
        btn.classList.add('border-slate-200', 'bg-white', 'text-slate-600');
      });
      button.classList.add('active', 'bg-tech-500', 'text-white');
      button.classList.remove('border-slate-200', 'bg-white', 'text-slate-600');
      renderProducts();
    });
  });
}

function initializeMenu() {
  const toggle = document.getElementById('mobileMenuToggle');
  const menu = document.getElementById('mobileMenu');
  toggle?.addEventListener('click', () => {
    menu?.classList.toggle('hidden');
  });
}

function initializeColorMode() {
  const toggle = document.querySelector('[data-color-toggle]');
  const applyMode = (mode) => {
    const dark = mode === 'dark';
    document.documentElement.dataset.colorMode = dark ? 'dark' : 'light';
    toggle?.setAttribute('aria-pressed', String(dark));
    toggle?.setAttribute('aria-label', dark ? 'العودة إلى الوضع الفاتح' : 'تفعيل الوضع الداكن');
    toggle?.setAttribute('title', dark ? 'العودة إلى الوضع الفاتح' : 'تفعيل الوضع الداكن');
  };

  let savedMode = localStorage.getItem(COLOR_MODE_KEY);
  if (savedMode === 'monochrome') {
    savedMode = 'dark';
    localStorage.setItem(COLOR_MODE_KEY, savedMode);
  }
  applyMode(savedMode || 'dark');
  toggle?.addEventListener('click', () => {
    const nextMode = document.documentElement.dataset.colorMode === 'dark' ? 'light' : 'dark';
    localStorage.setItem(COLOR_MODE_KEY, nextMode);
    applyMode(nextMode);
  });
}

function initializeSecretAdmin() {
  const secret = document.querySelector('[data-secret-admin]');
  if (!secret) return;

  let taps = [];
  secret.addEventListener('click', () => {
    const now = Date.now();
    taps = taps.filter((time) => now - time < 3000);
    taps.push(now);
    if (taps.length >= 5) {
      window.location.href = '/admin';
    }
  });
}

function getCurrentUser() {
  return state.session || null;
}

function setCurrentUser(user) {
  state.session = user;
  persistState(state);
}

function renderProductAdminTable() {
  const table = document.getElementById('productAdminTable');
  if (!table) return;

  if (!state.products.length) {
    table.innerHTML = '<div class="rounded-2xl border border-dashed border-slate-300 bg-white p-4 text-sm text-slate-500">لا توجد منتجات حتى الآن.</div>';
    return;
  }

  table.innerHTML = state.products.map((product) => `
    <div class="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-3">
      <img src="${product.images[0]}" alt="${escapeHtml(product.name)}" loading="lazy" decoding="async" class="h-16 w-16 rounded-xl object-cover" />
      <div class="min-w-0 flex-1">
        <div class="truncate text-sm font-black text-slate-900">${escapeHtml(product.name)}</div>
        <div class="mt-1 text-[11px] text-slate-500">${escapeHtml(product.category)} • ${escapeHtml(product.price)}</div>
      </div>
      <div class="flex gap-2">
        <button type="button" class="edit-product-btn rounded-xl border border-slate-200 bg-slate-50 px-2 py-1 text-[10px] font-black text-slate-700" data-id="${product.id}">تعديل</button>
        <button type="button" class="delete-product-btn rounded-xl border border-red-200 bg-red-50 px-2 py-1 text-[10px] font-black text-red-600" data-id="${product.id}">حذف</button>
      </div>
    </div>
  `).join('');

  table.querySelectorAll('.edit-product-btn').forEach((button) => {
    button.addEventListener('click', () => fillProductForm(button.dataset.id));
  });

  table.querySelectorAll('.delete-product-btn').forEach((button) => {
    button.addEventListener('click', () => deleteProduct(button.dataset.id));
  });
}

function fillProductForm(productId) {
  const product = state.products.find((item) => item.id === productId);
  if (!product) return;

  document.getElementById('productId').value = product.id;
  document.getElementById('productName').value = product.name;
  document.getElementById('productCategory').value = product.category;
  document.getElementById('productPrice').value = product.price;
  document.getElementById('productOldPrice').value = product.oldPrice || '';
  document.getElementById('productBadge').value = product.badge || '';
  document.getElementById('productDescription').value = product.description;
  document.getElementById('productSpecs').value = (product.specs || []).join('\n');
  document.getElementById('productImages').value = '';
}

function resetProductForm() {
  document.getElementById('productForm').reset();
  document.getElementById('productId').value = '';
  document.getElementById('productImages').value = '';
}

function encodeSelectedFiles(files) {
  return Promise.all(Array.from(files).map((file) => new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve({ name: file.name, dataUrl: reader.result });
    reader.onerror = () => reject(new Error('فشل قراءة الصورة'));
    reader.readAsDataURL(file);
  })));
}

async function handleProductSubmit(event) {
  event.preventDefault();
  const user = getCurrentUser();
  if (!user || !user.permissions.includes('add') && !user.permissions.includes('edit')) {
    return;
  }

  const productId = document.getElementById('productId').value;
  const name = document.getElementById('productName').value.trim();
  const category = document.getElementById('productCategory').value;
  const price = document.getElementById('productPrice').value.trim();
  const oldPrice = document.getElementById('productOldPrice').value.trim();
  const badge = document.getElementById('productBadge').value.trim();
  const description = document.getElementById('productDescription').value.trim();
  const specs = document.getElementById('productSpecs').value.split('\n').map((line) => line.trim()).filter(Boolean);
  const files = document.getElementById('productImages').files;

  if (!name || !price || !description) {
    return;
  }

  let nextImages = [];
  if (files && files.length) {
    const uploaded = await encodeSelectedFiles(files);
    nextImages = uploaded.map((file) => file.dataUrl);
  } else {
    const existing = state.products.find((item) => item.id === productId);
    nextImages = existing ? existing.images : DEFAULT_PRODUCTS[0].images;
  }

  const previousProducts = [...state.products];
  if (productId) {
    state.products = state.products.map((product) => product.id === productId
      ? { ...product, name, category, price, oldPrice, badge, description, specs, images: nextImages }
      : product);
  } else {
    const newProduct = {
      id: `product-${Date.now()}`,
      name,
      category,
      price,
      oldPrice,
      badge,
      description,
      specs,
      images: nextImages.length ? nextImages : DEFAULT_PRODUCTS[0].images
    };
    state.products.unshift(newProduct);
  }

  try {
    await saveProductsToServer();
  } catch (error) {
    state.products = previousProducts;
    window.alert('لم يتم حفظ المنتج على الخادم. تأكد من تشغيل الموقع ثم حاول مرة أخرى قبل مشاركة الرابط.');
    return;
  }
  persistState(state);
  renderProducts();
  renderProductAdminTable();
  resetProductForm();
}

async function deleteProduct(productId) {
  const user = getCurrentUser();
  if (!user || !user.permissions.includes('delete')) return;
  const previousProducts = [...state.products];
  state.products = state.products.filter((product) => product.id !== productId);
  try {
    await saveProductsToServer();
  } catch (error) {
    state.products = previousProducts;
    window.alert('لم يتم حذف المنتج من الخادم. تأكد من تشغيل الموقع ثم حاول مرة أخرى.');
    return;
  }
  persistState(state);
  renderProducts();
  renderProductAdminTable();
}

function renderUserAdminList() {
  const list = document.getElementById('userAdminList');
  if (!list) return;

  const currentUser = getCurrentUser();
  const isSuperAdmin = currentUser && currentUser.role === 'super_admin';

  if (!isSuperAdmin) {
    list.innerHTML = '<div class="rounded-2xl border border-amber-200 bg-amber-50 p-3 text-sm font-bold text-amber-700">للمشرفين العاديين، يتم إخفاء إدارة المستخدمين والصلاحيات في الواجهة المصممة لحماية الوصول الحساس.</div>';
    return;
  }

  list.innerHTML = state.users.map((user) => `
    <div class="rounded-2xl border border-slate-200 bg-white p-3">
      <div class="flex items-center justify-between gap-3">
        <div>
          <div class="text-sm font-black text-slate-900">${escapeHtml(user.name)}</div>
          <div class="text-[11px] text-slate-500">@${escapeHtml(user.username)}</div>
        </div>
        <span class="rounded-full bg-tech-50 px-2 py-1 text-[10px] font-black text-tech-600">${escapeHtml(user.role)}</span>
      </div>
      <div class="mt-3 flex flex-wrap gap-1">
        ${(user.permissions || []).map((perm) => `<span class="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-black text-slate-600">${escapeHtml(perm)}</span>`).join('')}
      </div>
    </div>
  `).join('');
}

function handleUserSubmit(event) {
  event.preventDefault();
  const currentUser = getCurrentUser();
  if (!currentUser || currentUser.role !== 'super_admin') return;

  const name = document.getElementById('userName').value.trim();
  const username = document.getElementById('userUsername').value.trim();
  const password = document.getElementById('userPassword').value.trim();
  const role = document.getElementById('userRole').value;
  const permissions = Array.from(document.querySelectorAll('.user-permission:checked')).map((input) => input.value);

  if (!name || !username || !password) {
    return;
  }

  const existingUser = state.users.find((user) => user.username === username);

  if (existingUser) {
    existingUser.name = name;
    existingUser.password = password;
    existingUser.role = role;
    existingUser.permissions = permissions.length ? permissions : ['view'];
  } else {
    state.users.push({
      name,
      username,
      password,
      role,
      permissions: permissions.length ? permissions : ['view']
    });
  }

  persistState(state);
  renderUserAdminList();
  document.getElementById('userForm').reset();
  document.querySelectorAll('.user-permission').forEach((box) => box.checked = box.value === 'view');
}

function toggleAdminAccess() {
  const adminSection = document.getElementById('adminSection');
  const adminLoginView = document.getElementById('adminLoginView');
  const adminDashboardView = document.getElementById('adminDashboardView');

  if (!adminSection || !adminLoginView || !adminDashboardView) return;

  const currentUser = getCurrentUser();
  if (window.location.pathname === '/admin' || window.location.hash === '#admin') {
    adminSection.classList.remove('hidden');
    adminLoginView.classList.toggle('hidden', !!currentUser);
    adminDashboardView.classList.toggle('hidden', !currentUser);
  } else {
    adminSection.classList.add('hidden');
  }
}

async function handleAdminLogin(event) {
  event.preventDefault();
  const username = document.getElementById('adminUsername').value.trim();
  const password = document.getElementById('adminPassword').value.trim();
  const errorBox = document.getElementById('adminLoginError');

  try {
    const csrf = await fetch('/api/admin/csrf').then((r) => r.json());
    const response = await fetch('/api/admin/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf.csrf_token },
      body: JSON.stringify({ username, password })
    });
    if (!response.ok) throw new Error('login failed');
  } catch (error) {
    errorBox.textContent = 'تعذر تسجيل الدخول إلى الخادم. تحقق من بيانات الدخول وحاول مرة أخرى.';
    errorBox.classList.remove('hidden');
    return;
  }

  const user = { username, name: username, role: 'super_admin', permissions: ['view', 'add', 'edit', 'delete'] };
  setCurrentUser(user);
  errorBox.classList.add('hidden');
  toggleAdminAccess();
  try {
    const productsResponse = await fetch('/api/products');
    await productsResponse.json();
    await syncProductsWithServer();
    renderProducts();
    renderProductAdminTable();
  } catch (error) {
    errorBox.textContent = 'تعذر مزامنة المنتجات مع الخادم.';
    errorBox.classList.remove('hidden');
  }
  renderUserAdminList();
}

async function handleAdminLogout() {
  const csrf = await fetch('/api/admin/csrf').then((r) => r.json());
  await fetch('/api/admin/logout', { method: 'POST', headers: { 'X-CSRF-Token': csrf.csrf_token } });
  setCurrentUser(null);
  toggleAdminAccess();
  document.getElementById('adminLoginForm').reset();
}

function initAdminPage() {
  const adminLoginForm = document.getElementById('adminLoginForm');
  const productForm = document.getElementById('productForm');
  const userForm = document.getElementById('userForm');
  const logoutBtn = document.getElementById('adminLogoutBtn');
  const newProductBtn = document.getElementById('newProductBtn');
  const cancelEdit = document.getElementById('cancelProductEdit');

  adminLoginForm?.addEventListener('submit', handleAdminLogin);
  productForm?.addEventListener('submit', handleProductSubmit);
  userForm?.addEventListener('submit', handleUserSubmit);
  logoutBtn?.addEventListener('click', handleAdminLogout);
  newProductBtn?.addEventListener('click', resetProductForm);
  cancelEdit?.addEventListener('click', resetProductForm);

  renderProductAdminTable();
  renderUserAdminList();
  toggleAdminAccess();
}

function hydrateProductFromUrl() {
  const pathname = window.location.pathname;
  const match = pathname.match(/^\/product\/(.+)$/);
  const productId = match ? decodeURIComponent(match[1]) : new URLSearchParams(window.location.search).get('product');

  if (!productId) {
    updateProductMeta(null);
    return;
  }

  if (!pathname.startsWith('/product/')) {
    window.location.replace(productPageUrl(productId));
    return;
  }

  const product = state.products.find((item) => item.id === productId);
  if (!product) {
    updateProductMeta(null);
    return;
  }

  renderProductPage(product.id);
}

function renderProductPage(productId) {
  const product = state.products.find((item) => item.id === productId);
  if (!product) return;

  const page = document.getElementById('productDetailPage');
  if (!page) return;

  page.classList.remove('hidden');
  document.getElementById('productDetailTitle').textContent = product.name;
  document.getElementById('productDetailBadge').textContent = product.badge || 'منتج';
  document.getElementById('productDetailPrice').textContent = product.price;
  document.getElementById('productDetailOldPrice').textContent = product.oldPrice || '';
  document.getElementById('productDetailOldPrice').classList.toggle('hidden', !product.oldPrice);
  document.getElementById('productDetailDescription').textContent = product.description;
  document.getElementById('productDetailSpecs').innerHTML = (product.specs || []).map((item) => `<li class="flex items-center gap-2">${checkIconMarkup()}${escapeHtml(item)}</li>`).join('');
  document.getElementById('productDetailMainImage').src = product.images[0];
  document.getElementById('productDetailMainImage').alt = product.name;
  document.getElementById('productDetailThumbs').innerHTML = product.images.map((image, index) => `
    <button type="button" class="thumb-btn rounded-xl border ${index === 0 ? 'border-tech-500 bg-white' : 'border-slate-200 bg-white'} p-1 transition hover:border-tech-500" data-image="${image}">
      <img src="${image}" alt="${escapeHtml(product.name)}" class="h-20 w-full rounded-lg object-cover" />
    </button>
  `).join('');
  document.getElementById('productDetailBuyButton').href = WhatsAppLink(product.name);
  document.getElementById('productDetailShareLink').href = productShareUrl(product.id);
  document.getElementById('productDetailShareLink').setAttribute('data-product-id', product.id);
  updateProductMeta(product);

  document.getElementById('productDetailThumbs')?.querySelectorAll('.thumb-btn').forEach((button) => {
    button.addEventListener('click', () => {
      const mainImage = document.getElementById('productDetailMainImage');
      mainImage.src = button.dataset.image;
      document.getElementById('productDetailThumbs').querySelectorAll('.thumb-btn').forEach((thumb) => thumb.classList.remove('border-tech-500'));
      button.classList.add('border-tech-500');
    });
  });
}

document.addEventListener('DOMContentLoaded', async () => {
  initializeColorMode();
  initializeMotion();
  initializeMenu();
  initializeFilters();
  initializeSecretAdmin();
  try {
    await validateAdminSession();
  } catch (error) {
    setCurrentUser(null);
  }
  initAdminPage();
  try {
    await syncProductsWithServer();
  } catch (error) {
    console.error(error);
  }
  renderProducts();
  renderProductAdminTable();
  hydrateProductFromUrl();

  document.getElementById('closeModal')?.addEventListener('click', closeProductModal);
  document.getElementById('productDetailShareLink')?.addEventListener('click', (event) => {
    event.preventDefault();
    const productId = window.location.pathname.split('/').filter(Boolean).pop();
    shareProduct(productId);
  });
  document.getElementById('productModal')?.addEventListener('click', (event) => {
    if (event.target.id === 'productModal') {
      closeProductModal();
    }
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeProductModal();
  });

  if (window.location.pathname === '/admin' || window.location.hash === '#admin') {
    document.getElementById('adminSection')?.classList.remove('hidden');
  }

});

