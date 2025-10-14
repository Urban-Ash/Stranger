// 编辑与删除模块：负责编辑模态框、更新与删除逻辑
import { showToast } from './utils.js';
import { t } from './i18n.js?v=2';
import { displayResults, displayNoResults } from './search.js?v=5';
import { renderStatusPanel, bindRetry } from './status_panel.js';
import { requestJson } from './api.js';
import { splitCommaList } from './utils.js';

export function openEditModal(result, index) {
  const editModal = document.getElementById('editModal');
  const editForm = document.getElementById('editDataForm');

  document.getElementById('editName').value = result.name || '';
  document.getElementById('editIdCard').value = result.id_card || '';
  document.getElementById('editPhones').value = Array.isArray(result.phones) ? result.phones.join(', ') : result.phones || '';
  document.getElementById('editQqs').value = Array.isArray(result.qqs) ? result.qqs.join(', ') : result.qqs || '';
  document.getElementById('editWeiboUid').value = result.weibo_uid || '';
  document.getElementById('editEmail').value = result.email || '';
  document.getElementById('editGender').value = result.gender || '';
  document.getElementById('editBirthDate').value = result.birth_date || '';
  document.getElementById('editLocation').value = result.location || '';
  document.getElementById('editCompany').value = result.company || '';
  document.getElementById('editPosition').value = result.position || '';
  document.getElementById('editIndustry').value = result.industry || '';
  document.getElementById('editCustomInfo').value = result.custom_info || '';
  document.getElementById('editDataSources').value = '';

  populateExistingSources(result, index);
  editForm.dataset.editIndex = index;
  editModal.style.display = 'block';
}

function populateExistingSources(result, resultIndex) {
  const sourcesList = document.getElementById('sourcesList');
  sourcesList.innerHTML = '';

  let dataSources = result.data_sources;
  if (typeof dataSources === 'string') {
    dataSources = dataSources.split(',').map((s) => s.trim()).filter((s) => s);
  }
  if (!Array.isArray(dataSources) || dataSources.length === 0) {
    sourcesList.innerHTML = '<div class="no-sources">暂无数据来源</div>';
    return;
  }

  dataSources.forEach((source, sourceIndex) => {
    const sourceName = typeof source === 'object' ? source.source : source;
    const capturedAt = typeof source === 'object' && source.captured_at ? new Date(source.captured_at).toLocaleDateString('zh-CN') : '';
    const displayText = capturedAt ? `${sourceName} (${capturedAt})` : sourceName;

    const sourceItem = document.createElement('div');
    sourceItem.className = 'edit-source-item';
    sourceItem.innerHTML = `
      <span class="edit-source-text">${displayText}</span>
      <span class="edit-source-delete" data-result-index="${resultIndex}" data-source-index="${sourceIndex}" title="删除此数据来源">×</span>
    `;
    sourcesList.appendChild(sourceItem);
  });

  sourcesList.addEventListener('click', (e) => {
    if (e.target.classList.contains('edit-source-delete')) {
      const ri = parseInt(e.target.dataset.resultIndex);
      const si = parseInt(e.target.dataset.sourceIndex);
      deleteSourceFromModal(ri, si);
    }
  });
}

function deleteSourceFromModal(resultIndex, sourceIndex) {
  if (!window.searchResults || !window.searchResults[resultIndex]) return;
  const result = window.searchResults[resultIndex];

  if (confirm('确定要删除这个数据来源吗？')) {
    let dataSources = result.data_sources;
    if (typeof dataSources === 'string') {
      dataSources = dataSources.split(',').map((s) => s.trim()).filter((s) => s);
    }
    if (Array.isArray(dataSources)) {
      dataSources.splice(sourceIndex, 1);
      const id = result._id || result.id;
      const updateData = { data_sources: dataSources };

      fetch(`/api/customer/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(updateData) })
        .then((r) => r.json())
        .then((data) => {
          if (data.success) {
            result.data_sources = dataSources;
            populateExistingSources(result, resultIndex);
            displayResults(window.searchResults);
            showToast('数据来源删除成功');
          } else {
            showToast('删除失败: ' + (data.message || '未知错误'));
          }
        })
        .catch(() => showToast('删除失败，请检查网络连接'));
    }
  }
}

export function closeEditModal() {
  const editModal = document.getElementById('editModal');
  if (editModal) editModal.style.display = 'none';
}

export function bindEditModalEvents() {
  const editModal = document.getElementById('editModal');
  const closeEditModal_btn = document.getElementById('closeEditModal');
  const cancelEdit = document.getElementById('cancelEdit');
  const deleteRecord = document.getElementById('deleteRecord');
  const editForm = document.getElementById('editDataForm');

  if (closeEditModal_btn) closeEditModal_btn.addEventListener('click', closeEditModal);
  if (cancelEdit) cancelEdit.addEventListener('click', closeEditModal);

  if (deleteRecord) {
    deleteRecord.addEventListener('click', () => {
      const editIndex = parseInt(editForm.dataset.editIndex);
      if (isNaN(editIndex) || !window.searchResults || !window.searchResults[editIndex]) {
        showToast(t('delete_failed'));
        return;
      }
      const record = window.searchResults[editIndex];
      const customerName = record.name || '未知';
      if (confirm(`确定要删除客户 "${customerName}" 的记录吗？\n\n此操作不可撤销！`)) {
        deleteCustomerRecord(record.customer_id || record.id || record._id, editIndex);
      }
    });
  }

  if (editModal) {
    editModal.addEventListener('click', (e) => {
      if (e.target === editModal) closeEditModal();
    });
  }

  if (editForm) {
    editForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const editIndex = parseInt(editForm.dataset.editIndex);
      if (isNaN(editIndex) || !window.searchResults || !window.searchResults[editIndex]) {
        showToast(t('edit_failed_prefix') + t('error_title'));
        return;
      }
      const result = window.searchResults[editIndex];
      const formData = new FormData(editForm);
      const updatedData = {};

      for (let [key, value] of formData.entries()) {
        value = value.trim();
        if (['phones', 'qqs'].includes(key)) {
          updatedData[key] = splitCommaList(value);
        } else if (key === 'data_sources') {
          if (value) {
            const newSources = value.split(',').map((v) => v.trim()).filter((v) => v);
            const existingSources = result.data_sources || [];
            const newSourceObjects = newSources.map((source) => ({ source, captured_at: new Date().toISOString() }));
            updatedData[key] = [...existingSources, ...newSourceObjects];
          } else {
            updatedData[key] = result.data_sources || [];
          }
        } else {
          updatedData[key] = value;
        }
      }

      const id = result._id || result.id;
      const statusEl = document.getElementById('editStatus');
      if (statusEl) renderStatusPanel(statusEl, { type: 'loading', title: t('loading') });
      requestJson(`/api/customer/${id}`, { method: 'PUT', body: updatedData })
        .then((data) => {
          if (data.success) {
            Object.assign(window.searchResults[editIndex], updatedData);
            if (statusEl) {
              renderStatusPanel(statusEl, { type: 'success_edit' });
            }
            setTimeout(() => {
              if (statusEl) statusEl.innerHTML = '';
              closeEditModal();
              displayResults(window.searchResults);
            }, 800);
          } else {
            const msg = data.message || t('unknown');
            if (statusEl) {
              renderStatusPanel(statusEl, { type: 'error', retry: true, retryId: 'retryEditBtn', desc: msg });
              bindRetry(statusEl, () => editForm.dispatchEvent(new Event('submit')), 'retryEditBtn');
            } else {
              showToast(t('edit_failed_prefix') + msg);
            }
          }
        })
        .catch((error) => {
          const statusEl = document.getElementById('editStatus');
          if (statusEl) {
            if (error && error.status === 503) {
              renderStatusPanel(statusEl, { type: 'service_unavailable', retry: true, retryId: 'retryEditBtn' });
            } else if (error && error.name === 'TypeError') {
              renderStatusPanel(statusEl, { type: 'network_error', retry: true, retryId: 'retryEditBtn' });
            } else {
              renderStatusPanel(statusEl, { type: 'error', retry: true, retryId: 'retryEditBtn', desc: error.message });
            }
            bindRetry(statusEl, () => editForm.dispatchEvent(new Event('submit')), 'retryEditBtn');
          } else {
            showToast(t('edit_failed_prefix') + error.message);
          }
        });
    });
  }
}

export function deleteCustomerRecord(customerId, recordIndex) {
  if (!customerId) {
    const record = typeof recordIndex === 'number' && window.searchResults ? window.searchResults[recordIndex] : null;
    customerId = record ? record.customer_id || record.id || record._id : customerId;
  }
  if (!customerId) {
    showToast(t('delete_failed'));
    return;
  }

  const statusEl = document.getElementById('editStatus');
  if (statusEl) renderStatusPanel(statusEl, { type: 'loading', title: t('loading') });
  requestJson(`/api/customer/${customerId}`, { method: 'DELETE' })
    .then((result) => {
      if (result.success) {
        if (statusEl) {
          renderStatusPanel(statusEl, { type: 'success_delete' });
        }
        setTimeout(() => {
          closeEditModal();
        }, 600);
        if (window.searchResults && typeof recordIndex === 'number' && recordIndex >= 0 && recordIndex < window.searchResults.length) {
          window.searchResults.splice(recordIndex, 1);
          const resultsContentEl = document.getElementById('resultsContent');
          if (window.searchResults.length === 0) {
            displayNoResults(resultsContentEl);
          } else {
            displayResults(window.searchResults);
          }
        }
        if (statusEl) statusEl.innerHTML = '';
      } else {
        const msg = result.message || result.error || t('delete_failed');
        if (statusEl) {
          renderStatusPanel(statusEl, { type: 'error', retry: true, retryId: 'retryDeleteBtn', desc: msg });
          bindRetry(statusEl, () => deleteCustomerRecord(customerId, recordIndex), 'retryDeleteBtn');
        } else {
          showToast(msg);
        }
      }
    })
    .catch((err) => {
      const statusEl = document.getElementById('editStatus');
      if (statusEl) {
        if (err && err.status === 503) {
          renderStatusPanel(statusEl, { type: 'service_unavailable', retry: true, retryId: 'retryDeleteBtn' });
        } else if (err && err.name === 'TypeError') {
          renderStatusPanel(statusEl, { type: 'network_error', retry: true, retryId: 'retryDeleteBtn' });
        } else {
          renderStatusPanel(statusEl, { type: 'error', retry: true, retryId: 'retryDeleteBtn', desc: t('delete_failed') });
        }
        bindRetry(statusEl, () => deleteCustomerRecord(customerId, recordIndex), 'retryDeleteBtn');
      } else {
        showToast(t('delete_failed'));
      }
    });
}