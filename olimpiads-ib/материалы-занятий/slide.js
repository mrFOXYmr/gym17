/* Slide deck controller: nav, progress, numbering, animation */
let idx = 0;
const slides = document.querySelectorAll('section');

function show() {
  slides.forEach((s, i) => {
    const on = (i === idx);
    s.style.display = on ? 'block' : 'none';
    s.classList.toggle('show', on);
    s.dataset.n = (i + 1) + ' / ' + slides.length;
  });
  const pg = document.getElementById('pg');
  if (pg) pg.textContent = (idx + 1) + ' / ' + slides.length;
  const pb = document.getElementById('progress');
  if (pb) pb.style.width = ((idx + 1) / slides.length * 100) + '%';
  if (window.scrollTo) window.scrollTo(0, 0);
}

function nav(d) {
  idx = Math.min(Math.max(idx + d, 0), slides.length - 1);
  show();
}
function go(i) { idx = Math.min(Math.max(i, 0), slides.length - 1); show(); }

document.addEventListener('keydown', (e) => {
  if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'PageDown') { nav(1); e.preventDefault(); }
  else if (e.key === 'ArrowLeft' || e.key === 'PageUp') { nav(-1); e.preventDefault(); }
  else if (e.key === 'Home') { go(0); }
  else if (e.key === 'End') { go(slides.length - 1); }
});

document.addEventListener('touchstart', (e) => { t0 = e.touches[0].clientX; });
let t0 = 0;
document.addEventListener('touchend', (e) => {
  const dx = e.changedTouches[0].clientX - t0;
  if (Math.abs(dx) > 45) nav(dx < 0 ? 1 : -1);
});

/* progress bar element */
const pb = document.createElement('div');
pb.id = 'progress';
document.body.appendChild(pb);

show();