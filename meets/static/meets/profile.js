const search = document.querySelector('#class-search');
const choices = [...document.querySelectorAll('.class-options label')];
function filter() {
  let visible = 0;
  let selected = 0;
  for (const label of choices) {
    label.hidden = !label.textContent.toLowerCase().includes(search.value.trim().toLowerCase());
    if (!label.hidden) visible++;
    if (label.querySelector('input').checked) selected++;
  }
  document.querySelector('#selected-count').textContent = visible ? selected + ' kelas dipilih' : 'Tidak ada kelas yang cocok.';
}
search.addEventListener('input', filter);
document.querySelector('.class-options').addEventListener('change', filter);
filter();
document.querySelector('[name=photo]').addEventListener('change', event => {
  const file = event.target.files[0];
  event.target.setCustomValidity('');
  if (!file) return;
  if (file.size > 2*1024*1024) {
    event.target.setCustomValidity('Pilih foto hingga 2 MB.');
    event.target.reportValidity();
  } else {
    event.target.setCustomValidity('');
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => { document.querySelector('.portrait').replaceChildren(img); URL.revokeObjectURL(url); };
    img.onerror = () => URL.revokeObjectURL(url);
    img.alt = 'Pratinjau foto baru';
    img.src = url;
  }
});
