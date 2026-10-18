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
    var img = '<img src="' + imgUrl(w.img, 480, h480) + '" alt="' + esc(title) + ' — ' + esc(type) + '" width="' + w.w + '" height="' + w.h + '" loading="lazy" decoding="async">';
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

    function render() {
      var list = base.filter(function (w) { return state.kind === 'all' || w.kind === state.kind; });
      var visible = (limit && !state.expanded) ? list.slice(0, limit) : list;
      grid.innerHTML = visible.length ? visible.map(card).join('') : '<p class="work-empty">' + L.none + '</p>';
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
