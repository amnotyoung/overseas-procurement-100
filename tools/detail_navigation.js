const listState = new URLSearchParams(location.search).get('list');
if (listState !== null) {
  const input = new URLSearchParams(listState);
  const state = new URLSearchParams();
  for (const key of ['country', 'axis', 'q']) if (input.get(key)) state.set(key, input.get(key));
  const listLink = document.querySelector('header.site nav a');
  const back = document.querySelector('#catalog-return');
  if (back && listLink) {
    const href = '../../index.html' + (state.size ? '?' + state.toString() : '') + '#results';
    back.href = listLink.href = href;
    back.textContent = '보고 있던 목록으로 돌아가기';
    for (const link of document.querySelectorAll('a[href^="../"]')) {
      const url = new URL(link.href);
      if (url.pathname.includes('/model/')) {
        url.searchParams.set('list', state.toString());
        link.href = url.href;
      }
    }
  }
}
const selector = document.querySelector('#sel');
if (selector) selector.addEventListener('change', () => {
  const url = new URL('../' + selector.value + '/index.html', location.href);
  if (listState !== null) url.searchParams.set('list', listState);
  location.assign(url.href);
});
document.querySelector('#copy-steps').addEventListener('click', async () => {
  const list = document.querySelector('#readable-steps');
  const status = document.querySelector('#copy-status');
  const text = [...list.children].map((item, i) => (i + 1) + '. ' + item.textContent.trim()).join('\n');
  try {
    await navigator.clipboard.writeText(text);
    status.textContent = '단계 목록을 복사했습니다.';
  } catch {
    const range = document.createRange();
    range.selectNodeContents(list);
    const selection = getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    status.textContent = '목록을 선택했습니다. 기기의 복사 기능을 사용하세요.';
  }
});
