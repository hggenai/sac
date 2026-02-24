/**
 * 営業管理アプリ - メインJS
 */

document.addEventListener('DOMContentLoaded', function () {

  // ─── Bootstrap Tooltip初期化 ───
  const tooltipEls = document.querySelectorAll('[data-bs-toggle="tooltip"]');
  tooltipEls.forEach(el => new bootstrap.Tooltip(el));

  // ─── フラッシュメッセージ自動消去 (4秒後) ───
  document.querySelectorAll('.alert-dismissible').forEach(el => {
    setTimeout(() => {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(el);
      if (bsAlert) bsAlert.close();
    }, 4000);
  });

  // ─── 教授一覧: 大学→学科連動フィルター ───
  const univFilter = document.querySelector('select[name="university_id"]');
  const deptFilter = document.querySelector('select[name="dept_id"]');
  if (univFilter && deptFilter) {
    function filterDepts() {
      const univId = univFilter.value;
      Array.from(deptFilter.options).forEach(opt => {
        if (!opt.value) { opt.hidden = false; return; }
        opt.hidden = univId && opt.dataset.univ !== univId;
      });
    }
    univFilter.addEventListener('change', filterDepts);
    filterDepts();
  }

  // ─── 印刷ビュー: 教授フォームの学科絞り込み ───
  const univSelect = document.getElementById('univ-select');
  const deptSelect = document.getElementById('dept-select');
  if (univSelect && deptSelect) {
    univSelect.addEventListener('change', function () {
      const univId = this.value;
      Array.from(deptSelect.options).forEach(opt => {
        if (!opt.value) { opt.hidden = false; return; }
        opt.hidden = univId && opt.dataset.univ !== univId;
      });
      deptSelect.value = '';
    });
  }

  // ─── カスタムフィールド: 種類に応じてオプション欄表示 ───
  const ftSelect = document.getElementById('field-type-select');
  const optGroup = document.getElementById('options-group');
  if (ftSelect && optGroup) {
    ftSelect.addEventListener('change', function () {
      optGroup.style.display = this.value === 'select' ? 'block' : 'none';
    });
  }

  // ─── 確認ダイアログ: data-confirm属性 ───
  document.querySelectorAll('[data-confirm]').forEach(el => {
    el.addEventListener('click', function (e) {
      if (!confirm(this.dataset.confirm)) e.preventDefault();
    });
  });

});
