const searchBox = document.querySelector('#q');
const countrySelect = document.querySelector('#country-select');
const filterButtons = [...document.querySelectorAll('.side button[data-f]')];
const rows = [...document.querySelector('#tb').rows];
const guides = [...document.querySelectorAll('.writing-route')];
const params = new URLSearchParams(location.search);
const filters = {c: '', a: ''};
for (const [key, parameter] of [['c', 'country'], ['a', 'axis']]) {
  const value = params.get(parameter);
  if (filterButtons.some(button => button.dataset.f === key && button.dataset.v === value)) filters[key] = value;
}
searchBox.value = params.get('q') || '';

function applyFilters() {
  const term = searchBox.value.trim().toLowerCase();
  let count = 0;
  for (const row of rows) {
    row.hidden = Boolean((filters.c && row.dataset.c !== filters.c) ||
      (filters.a && row.dataset.a !== filters.a) || (term && !row.dataset.s.includes(term)));
    if (!row.hidden) count++;
  }
  for (const group of guides) group.hidden = group.dataset.country !== filters.c;
  countrySelect.value = filters.c;
  for (const button of filterButtons) button.setAttribute('aria-pressed', String(filters[button.dataset.f] === button.dataset.v));
  document.querySelector('#cnt').textContent = (term || filters.c || filters.a) ? count + '건 표시' : '전체 ' + count + '건';
  document.querySelector('#hcnt').textContent = count;
  document.querySelector('#none').hidden = count > 0;
  const state = new URLSearchParams();
  if (filters.c) state.set('country', filters.c);
  if (filters.a) state.set('axis', filters.a);
  if (searchBox.value) state.set('q', searchBox.value);
  const current = new URL(location.href);
  for (const key of ['country', 'axis', 'q']) current.searchParams.delete(key);
  for (const [key, value] of state) current.searchParams.set(key, value);
  try { history.replaceState(history.state, '', current); } catch {}
  // A link also carries the selection when opened in a new tab or copied.
  const suffix = '?list=' + encodeURIComponent(state.toString());
  for (const link of document.querySelectorAll('#tb tr:not([hidden]) a, .writing-route:not([hidden]) a')) {
    const base = link.dataset.base || (link.dataset.base = link.getAttribute('href'));
    const [path, fragment] = base.split('#');
    link.setAttribute('href', path + suffix + (fragment ? '#' + fragment : ''));
  }
}
searchBox.addEventListener('input', applyFilters);
countrySelect.addEventListener('change', () => { filters.c = countrySelect.value; applyFilters(); });
for (const button of filterButtons) button.addEventListener('click', () => {
  filters[button.dataset.f] = button.dataset.v;
  applyFilters();
});
applyFilters();
const scrollKey = () => 'catalog-scroll:' + location.pathname.replace(/index\.html$/, '') + ':' +
  new URLSearchParams([...new URLSearchParams(location.search)].filter(([key]) => ['country','axis','q'].includes(key))).toString();
addEventListener('pagehide', () => {
  try { sessionStorage.setItem(scrollKey(), String(scrollY)); } catch {}
});
if (location.hash === '#results') {
  let saved = null;
  try { saved = sessionStorage.getItem(scrollKey()); } catch {}
  if (saved !== null) requestAnimationFrame(() => scrollTo(0, Number(saved)));
}
