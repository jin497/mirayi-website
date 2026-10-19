/* Renders every [data-portfolio] block from assets/works.js
   data-limit="12"      show 12 first, then a "View all works" button
   data-filters="true"  show the All / Mirayi IP / Services work toggle
   data-kinds="ip"      only show this kind (ip | service)
   data-cats="commercial,series"  only show these categories */
(function () {
  'use strict';

  var cfg = window.MIRAYI || {};
  var lang = ((document.documentElement.lang || 'en').slice(0, 2)).toLowerCase();
  var LS = {
    zh: { all: '全部作品', ip: 'Mirayi 原创IP', service: '服务项目', watch: '观看', watchLabel: '观看', opens: '（打开视频链接）',
          viewAll: function (n) { return '查看全部 ' + n + ' 个作品'; }, fewer: '收起作品', none: '暂无作品。', ipTag: 'Mirayi 原创IP' },
    ko: { all: '전체 작품', ip: 'Mirayi IP', service: '제작 서비스', watch: '보기', watchLabel: '보기', opens: ' (영상 링크가 열립니다)',
          viewAll: function (n) { return '작품 ' + n + '개 모두 보기'; }, fewer: '작품 접기', none: '표시할 작품이 없습니다.', ipTag: 'Mirayi 오리지널 IP' },
    ja: { all: 'すべての作品', ip: 'Mirayi IP', service: '制作サービス', watch: '再生', watchLabel: '再生', opens: '（動画リンクが開きます）',
          viewAll: function (n) { return '全' + n + '作品を表示'; }, fewer: '作品を折りたたむ', none: '表示する作品がありません。', ipTag: 'Mirayi オリジナルIP' }
  };
  var L = LS[lang] || {
    all: 'All works', ip: 'Mirayi IP', service: 'Services work', watch: 'Watch', watchLabel: 'Watch', opens: ' (opens YouTube)',
    viewAll: function (n) { return 'View all ' + n + ' works'; }, fewer: 'Show fewer works', none: 'No works to show yet.', ipTag: 'Mirayi IP'
  };
  var FK = { zh: ['tz', 'xz', 'nz', 'vz'], ko: ['tk', 'xk', 'nk', 'vk'], ja: ['tj', 'xj', 'nj', 'vj'] }[lang] || [];
  var works = window.MIRAYI_WORKS || [];
  var SHAPE = { poster: 2 / 3, landscape: 16 / 9, square: 1 };
  var FOCUS = { top: '50% 0%', bottom: '50% 100%', left: '0% 50%', right: '100% 50%' };
  function shapeOf(w) { var s = w.s || window.MIRAYI_THUMB || 'natural'; return SHAPE[s] ? s : 'natural'; }
  function ratioOf(w) { var s = shapeOf(w); return s === 'natural' ? w.w / w.h : SHAPE[s]; }

  // base address of the site (works on the live site and when opening the _preview folder from disk)
  var sc = document.querySelector('script[src$="works.js"]');
  var base = sc && sc.src ? sc.src.replace(/assets\/works\.js.*$/, '') : '/';

  function imgUrl(id, w, h) {
    if (/^https?:/.test(id)) return id;
    if (id.charAt(0) === '/') return base + id.slice(1);
    if (cfg.localImages) return '/assets/img/' + id.replace(/~/g, '-');
    return 'https://static.wixstatic.com/media/' + id + '/v1/fill/w_' + w + ',h_' + h + ',al_c,q_85/' + id;
  }

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function card(w) {
    var h480 = Math.round(480 * w.h / w.w);
    var title = (FK[0] && w[FK[0]]) || w.t, type = (FK[1] && w[FK[1]]) || w.type, note = (FK[2] && w[FK[2]]) || w.note, video = (FK[3] && w[FK[3]]) || w.video;
    var tag = w.kind === 'ip' ? '<em class="tag">' + esc(note || L.ipTag) + '</em>' : (note ? '<em class="tag">' + esc(note) + '</em>' : '');
    var shp = shapeOf(w), r = ratioOf(w);
    var crop = shp !== 'natural';
    var img = '<img' + (crop ? ' class="crop" style="aspect-ratio:' + r.toFixed(4) + (FOCUS[w.f] ? ';object-position:' + FOCUS[w.f] : '') + '"' : '') + ' src="' + imgUrl(w.img, 480, crop ? Math.round(480 / r) : h480) + '" alt="' + esc(title) + ' — ' + esc(type) + '" width="' + (crop ? 480 : w.w) + '" height="' + (crop ? Math.round(480 / r) : w.h) + '" loading="lazy" decoding="async">';
    var media = video
      ? '<a class="work-media" href="' + esc(video) + '" target="_blank" rel="noopener noreferrer" aria-label="' + L.watchLabel + ' ' + esc(title) + L.opens + '">' + img + '<span class="play">' + L.watch + '</span></a>'
      : '<div class="work-media">' + img + '</div>';
    return '<figure class="work">' + media + tag + '<figcaption><strong>' + esc(title) + '</strong><span>' + esc(type) + '</span></figcaption></figure>';
  }

  document.querySelectorAll('[data-portfolio]').forEach(function (root) {
    var kinds = (root.dataset.kinds || '').split(',').filter(Boolean);
    var cats = (root.dataset.cats || '').split(',').filter(Boolean);
    var limit = parseInt(root.dataset.limit || '0', 10);
    var showFilters = root.dataset.filters === 'true';

    var base = works.filter(function (w) {
      return (!kinds.length || kinds.indexOf(w.kind) > -1) && (!cats.length || cats.indexOf(w.cat) > -1);
    });

    var state = { kind: 'all', expanded: false };
    var grid = root.querySelector('.work-grid');
    var more = root.querySelector('.work-more');
    var moreBtn = more && more.querySelector('button');
    var bar = root.querySelector('.work-filters');

    function count(kind) {
      return base.filter(function (w) { return kind === 'all' || w.kind === kind; }).length;
    }

    if (bar && showFilters) {
      [['all', L.all], ['ip', L.ip], ['service', L.service]].forEach(function (f) {
        var b = document.createElement('button');
        b.type = 'button';
        b.dataset.kind = f[0];
        b.textContent = f[1] + ' (' + count(f[0]) + ')';
        b.setAttribute('aria-pressed', f[0] === 'all' ? 'true' : 'false');
        b.addEventListener('click', function () {
          state.kind = f[0];
          state.expanded = false;
          bar.querySelectorAll('button').forEach(function (x) {
            x.setAttribute('aria-pressed', x === b ? 'true' : 'false');
          });
          render();
        });
        bar.appendChild(b);
      });
    } else if (bar) {
      bar.hidden = true;
    }

    // Places the cards into columns, each next card going into the currently shortest column, so the order set in
    // the editor reads left to right, row by row.
    var cols = 0, last = [];
    function colCount() {
      var wd = grid.clientWidth || root.clientWidth || 1000;
      return Math.max(2, Math.min(5, Math.floor((wd + 14) / 184)));
    }
    function layout(list) {
      last = list;
      if (!list.length) { grid.innerHTML = '<p class="work-empty">' + L.none + '</p>'; return; }
      cols = colCount();
      var heights = [], parts = [];
      for (var i = 0; i < cols; i++) { heights.push(0); parts.push(''); }
      list.forEach(function (w) {
        var k = 0;
        for (var i = 1; i < cols; i++) { if (heights[i] < heights[k] - 0.001) k = i; }
        parts[k] += card(w);
        heights[k] += 1 / ratioOf(w) + 0.22;
      });
      grid.innerHTML = parts.map(function (p) { return '<div class="work-col">' + p + '</div>'; }).join('');
    }
    var rt;
    window.addEventListener('resize', function () {
      clearTimeout(rt);
      rt = setTimeout(function () { if (last.length && colCount() !== cols) layout(last); }, 150);
    });

    function render() {
      var list = base.filter(function (w) { return state.kind === 'all' || w.kind === state.kind; });
      var visible = (limit && !state.expanded) ? list.slice(0, limit) : list;
      layout(visible);
      if (more && moreBtn) {
        var needed = limit && list.length > limit;
        more.hidden = !needed;
        moreBtn.setAttribute('aria-expanded', state.expanded ? 'true' : 'false');
        moreBtn.textContent = state.expanded ? L.fewer : L.viewAll(list.length);
      }
    }

    if (moreBtn) {
      moreBtn.addEventListener('click', function () {
        state.expanded = !state.expanded;
        render();
        if (!state.expanded) root.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    }

    render();
  });
})();
