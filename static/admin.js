// تأكيد الحذف في لوحة الإدارة.
document.addEventListener('submit', function (event) {
  var message = event.target.getAttribute('data-confirm');
  if (message && !window.confirm(message)) event.preventDefault();
});

// اختيار دور جاهز يملأ خانات الصلاحيات، وتعديل الخانات يدوياً يحوّل الدور إلى «مخصص».
(function () {
  var select = document.querySelector('[data-role-select]');
  if (!select) return;
  var boxes = Array.prototype.slice.call(document.querySelectorAll('[data-perm]'));
  select.addEventListener('change', function () {
    var option = select.options[select.selectedIndex];
    if (option.value === 'custom') return;
    var perms = (option.dataset.perms || '').split(',');
    boxes.forEach(function (b) { b.checked = perms.indexOf(b.dataset.perm) !== -1; });
  });
  boxes.forEach(function (b) {
    b.addEventListener('change', function () { select.value = 'custom'; });
  });
})();
