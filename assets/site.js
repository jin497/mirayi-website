/* Mobile menu + contact form */
(function () {
  'use strict';

  var btn = document.querySelector('.menu-btn');
  var nav = document.getElementById('nav');
  if (btn && nav) {
    btn.addEventListener('click', function () {
      var open = nav.classList.toggle('open');
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }

  var hs = document.querySelector('.hero-slider');
  if (hs) {
    var slides = hs.querySelectorAll('.slide'), dots = hs.querySelector('.hs-dots'), cur = 0, timer;
    var show = function (n) {
      cur = (n + slides.length) % slides.length;
      slides.forEach(function (s, i) { s.classList.toggle('on', i === cur); });
      dots.querySelectorAll('button').forEach(function (d, i) { d.setAttribute('aria-current', i === cur ? 'true' : 'false'); });
    };
    slides.forEach(function (_, i) {
      var d = document.createElement('button');
      d.type = 'button'; d.setAttribute('aria-label', 'Show slide ' + (i + 1));
      d.addEventListener('click', function () { show(i); restart(); });
      dots.appendChild(d);
    });
    var restart = function () {
      clearInterval(timer);
      if (!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches)) timer = setInterval(function () { show(cur + 1); }, Math.max(1, parseFloat(hs.dataset.seconds) || 5) * 1000);
    };
    hs.querySelector('.prev').addEventListener('click', function () { show(cur - 1); restart(); });
    hs.querySelector('.next').addEventListener('click', function () { show(cur + 1); restart(); });
    var loadRest = function () {
      slides.forEach(function (im) { if (im.dataset.src) { im.src = im.dataset.src; im.removeAttribute('data-src'); } });
    };
    if (document.readyState === 'complete') loadRest(); else window.addEventListener('load', loadRest);
    show(0); restart();
  }


  // Social cards: load Facebook / LinkedIn only after a click (keeps the page fast and private)
  document.addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('.embed-load');
    if (!b) return;
    var f = document.createElement('iframe');
    f.src = b.dataset.src;
    f.title = b.dataset.title || '';
    f.loading = 'lazy';
    f.setAttribute('allow', 'encrypted-media');
    f.setAttribute('referrerpolicy', 'no-referrer-when-downgrade');
    f.style.cssText = 'width:100%;height:' + (b.dataset.h || 500) + 'px;border:0;display:block;background:#fff';
    var box = b.parentNode;
    box.innerHTML = '';
    box.style.minHeight = '0';
    box.appendChild(f);
  });

  // Optional: load a social card as soon as it scrolls into view (only when switched on in /admin)
  var autoCards = document.querySelectorAll('.embed-card[data-auto]');
  if (autoCards.length && 'IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (en) {
        if (!en.isIntersecting) return;
        io.unobserve(en.target);
        var b = en.target.querySelector('.embed-load');
        if (b) b.click();
      });
    }, { rootMargin: '200px' });
    autoCards.forEach(function (c) { io.observe(c); });
  }

  // "What people say": numbered buttons, swipe, arrow keys and automatic next slide
  document.querySelectorAll('.tcar[data-seconds]').forEach(function (car) {
    var slides = car.querySelectorAll('.tc-slide');
    if (slides.length < 2) return;
    car.classList.add('js');
    var cur = 0, timer = null, paused = false;
    var secs = Math.max(2, parseFloat(car.dataset.seconds) || 8);
    var nav = document.createElement('div');
    nav.className = 'tc-nav';
    nav.setAttribute('role', 'group');
    var prev = document.createElement('button'), next = document.createElement('button');
    prev.type = next.type = 'button';
    prev.className = 'tc-arrow'; next.className = 'tc-arrow';
    prev.innerHTML = '&#8249;'; next.innerHTML = '&#8250;';
    prev.setAttribute('aria-label', car.dataset.prev || 'Previous');
    next.setAttribute('aria-label', car.dataset.next || 'Next');
    nav.appendChild(prev);
    var nums = [];
    slides.forEach(function (_, i) {
      var b = document.createElement('button');
      b.type = 'button'; b.className = 'tc-num'; b.textContent = String(i + 1);
      b.setAttribute('aria-label', (car.dataset.go || 'Show comment') + ' ' + (i + 1));
      b.addEventListener('click', function () { go(i); restart(); });
      nums.push(b); nav.appendChild(b);
    });
    nav.appendChild(next);
    car.appendChild(nav);
    function go(n) {
      cur = (n + slides.length) % slides.length;
      slides.forEach(function (s, i) { s.classList.toggle('on', i === cur); s.setAttribute('aria-hidden', i === cur ? 'false' : 'true'); });
      nums.forEach(function (b, i) { b.setAttribute('aria-current', i === cur ? 'true' : 'false'); });
    }
    function restart() {
      clearInterval(timer);
      if (paused || (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches)) return;
      timer = setInterval(function () { go(cur + 1); }, secs * 1000);
    }
    prev.addEventListener('click', function () { go(cur - 1); restart(); });
    next.addEventListener('click', function () { go(cur + 1); restart(); });
    car.addEventListener('mouseenter', function () { paused = true; clearInterval(timer); });
    car.addEventListener('mouseleave', function () { paused = false; restart(); });
    car.addEventListener('focusin', function () { paused = true; clearInterval(timer); });
    car.addEventListener('focusout', function () { paused = false; restart(); });
    car.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowLeft') { go(cur - 1); restart(); } else if (e.key === 'ArrowRight') { go(cur + 1); restart(); }
    });
    var x0 = null;
    car.addEventListener('pointerdown', function (e) { x0 = e.clientX; });
    car.addEventListener('pointerup', function (e) {
      if (x0 === null) return;
      var dx = e.clientX - x0; x0 = null;
      if (Math.abs(dx) > 40) { go(cur + (dx < 0 ? 1 : -1)); restart(); }
    });
    go(0); restart();
  });


  // Language: remember a manual choice, and on a first visit send people whose browser language is
  // Chinese / Korean / Japanese to the matching version of the same page (never for crawlers).
  (function () {
    var KEY = 'mirayi_lang';
    function get() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }
    function put(v) { try { localStorage.setItem(KEY, v); } catch (e) { /* ignore */ } }
    var sw = document.querySelector('.lang-switch');
    if (sw) {
      sw.addEventListener('click', function (e) {
        var a = e.target.closest ? e.target.closest('a') : null;
        if (a) put((a.getAttribute('lang') || 'en').slice(0, 2).toLowerCase());
      });
    }
    var here = (document.documentElement.lang || 'en').slice(0, 2).toLowerCase();
    if (here !== 'en' || !sw || get()) return;
    if (/bot|crawl|spider|slurp|bing|baidu|yandex|lighthouse/i.test(navigator.userAgent || '')) return;
    if (document.referrer) {
      try { if (new URL(document.referrer).host === location.host) return; } catch (e) { /* ignore */ }
    }
    var prefs = (navigator.languages && navigator.languages.length) ? navigator.languages : [navigator.language || 'en'];
    var target = '';
    for (var i = 0; i < prefs.length; i++) {
      var c = String(prefs[i]).slice(0, 2).toLowerCase();
      if (c === 'en') return;                       // English is the visitor's first choice: stay
      if (c === 'zh' || c === 'ko' || c === 'ja') { target = c; break; }
    }
    if (!target) return;
    var hl = { zh: 'zh-Hans', ko: 'ko', ja: 'ja' }[target];
    if (!document.querySelector('link[rel="alternate"][hreflang="' + hl + '"]')) return;   // this page has no translation
    var link = sw.querySelector('a[lang="' + target + '"]');
    if (link && link.getAttribute('href')) {
      put(target);
      location.replace(link.getAttribute('href'));
    }
  })();

  var form = document.querySelector('form[data-contact]');
  if (!form) return;
  var note = form.querySelector('.form-note');
  var cfg = window.MIRAYI || {};

  var lang = ((document.documentElement.lang || 'en').slice(0, 2)).toLowerCase();
  var MS = {
    zh: { sending: '发送中…', ok: '提交成功！我们已收到您的留言，会尽快回复。', err: '抱歉，发送失败，请稍后再试，或直接发邮件给我们。',
          mail: '正在打开您的邮件应用…', none: '联系表单尚未连接，请通过邮箱、飞书或微信联系我们。' },
    ko: { sending: '보내는 중…', ok: '전송되었습니다. 문의를 확인한 후 회신드리겠습니다.', err: '죄송합니다. 전송에 실패했습니다. 잠시 후 다시 시도하시거나 이메일로 문의해 주세요.',
          mail: '메일 앱을 여는 중…', none: '문의 양식이 아직 연결되지 않았습니다. 이메일로 문의해 주세요.' },
    ja: { sending: '送信中…', ok: '送信しました。内容を確認のうえ、ご連絡いたします。', err: '申し訳ありません。送信できませんでした。しばらくしてから再度お試しいただくか、メールでお問い合わせください。',
          mail: 'メールアプリを開いています…', none: 'お問い合わせフォームはまだ接続されていません。メールでご連絡ください。' }
  };
  var M = MS[lang] || {
    sending: 'Sending…', ok: 'Success! Message received.', err: 'Sorry, the message could not be sent. Please try again later.',
    mail: 'Opening your email app…', none: 'The contact form is not connected yet. Set formEndpoint or contactEmail in assets/config.js.'
  };

  function say(msg, cls) {
    if (!note) return;
    note.textContent = msg;
    note.className = 'form-note ' + (cls || '');
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var data = new FormData(form);

    if (cfg.formEndpoint) {
      say(M.sending);
      fetch(cfg.formEndpoint, { method: 'POST', body: data, headers: { Accept: 'application/json' } })
        .then(function (r) {
          if (!r.ok) throw new Error('bad status');
          form.reset();
          say(M.ok, 'ok');
        })
        .catch(function () {
          say(M.err, 'err');
        });
      return;
    }

    if (cfg.contactEmail) {
      var body = 'Name: ' + data.get('name') + '\nCompany: ' + data.get('company') +
                 '\nEmail: ' + data.get('email') + '\n\n' + data.get('message');
      window.location.href = 'mailto:' + cfg.contactEmail +
        '?subject=' + encodeURIComponent('Project enquiry from ' + data.get('name')) +
        '&body=' + encodeURIComponent(body);
      say(M.mail);
      return;
    }

    say(M.none, 'err');
  });
})();
