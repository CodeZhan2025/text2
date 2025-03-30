// 文件上传和审核相关的全局函数
function startAudit() {
  // 获取文件
  const fileInput = document.getElementById('file-input');
  const files = fileInput.files;
  if (files.length === 0) {
    alert('请先选择文件！');
    return;
  }

  const file = files[0];
  const formData = new FormData();
  formData.append('file', file);

  // 显示进度条模态框
  showProgressModal();

  // 发送文件到服务器
  fetch('/upload', {
    method: 'POST',
    body: formData
  })
    .then(response => response.json())
    .then(data => {
      if (data.error) {
        throw new Error(data.error);
      }

      if (data.task_id) {
        // 如果有任务ID，开始轮询进度
        const stepUpload = document.getElementById('step-upload');
        const stepProcessing = document.getElementById('step-processing');
        const stepComplete = document.getElementById('step-complete');
        const progressBar = document.getElementById('auditProgressBar');

        // 开始轮询进度
        pollProgress(data.task_id, {
          progressBar: progressBar,
          stepUpload: stepUpload,
          stepProcessing: stepProcessing,
          stepComplete: stepComplete,
          onComplete: function () {
            // 获取最终报告
            fetch(`/report/${data.task_id}`)
              .then(response => response.json())
              .then(reportData => {
                if (reportData.error) {
                  throw new Error(reportData.error);
                }
                setTimeout(() => {
                  hideProgressModal();
                  showReport(reportData.report);
                }, 500);
              })
              .catch(error => {
                console.error('获取报告失败:', error);
                hideProgressModal();
                alert('获取审核报告失败：' + error.message);
              });
          },
          onError: function (errorMsg) {
            console.error('审核错误:', errorMsg);
            hideProgressModal();
            alert('审核过程中出错：' + errorMsg);
          }
        });
      } else {
        // 如果没有任务ID，直接显示报告（旧版本兼容）
        updateProgress(100);
        setTimeout(() => {
          hideProgressModal();
          showReport(data.report);
        }, 500);
      }
    })
    .catch(error => {
      console.error('Error:', error);
      hideProgressModal();
      alert('上传失败：' + error.message);
    });
}

// 格式化文件大小
function formatFileSize(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 轮询进度
function pollProgress(taskId, options) {
  const {
    progressBar,
    stepUpload,
    stepProcessing,
    stepComplete,
    onComplete,
    onError
  } = options;

  const poll = () => {
    fetch(`/progress/${taskId}`)
      .then(response => response.json())
      .then(data => {
        if (data.error) {
          onError(data.error);
          return;
        }

        // 更新进度条
        progressBar.style.width = `${data.progress}%`;

        // 更新步骤状态
        switch (data.status) {
          case 'uploading':
            stepUpload.classList.add('active');
            stepUpload.querySelector('.step-status').textContent = data.message;
            break;
          case 'reading':
            stepUpload.classList.add('completed');
            stepProcessing.classList.add('active');
            stepProcessing.querySelector('.step-status').textContent = data.message;
            break;
          case 'processing':
          case 'analyzing':
            stepUpload.classList.add('completed');
            stepProcessing.classList.add('active');
            stepProcessing.querySelector('.step-status').textContent = data.message;
            break;
          case 'completed':
            stepUpload.classList.add('completed');
            stepProcessing.classList.add('completed');
            stepComplete.classList.add('completed');
            stepComplete.querySelector('.step-status').textContent = data.message;
            onComplete();
            return;
          case 'error':
            onError(data.message);
            return;
        }

        // 继续轮询
        setTimeout(poll, 1000);
      })
      .catch(error => {
        console.error('轮询错误:', error);
        onError(error.message);
      });
  };

  // 开始轮询
  poll();
}

// 进度条相关全局函数
function showProgressModal() {
  const progressModal = document.getElementById('auditProgressModal');
  if (progressModal) {
    progressModal.classList.remove('hidden');

    // 更新文件信息
    const fileInput = document.getElementById('file-input');
    const auditFileName = document.getElementById('auditFileName');
    const auditFileSize = document.getElementById('auditFileSize');

    if (fileInput.files.length > 0 && auditFileName && auditFileSize) {
      const file = fileInput.files[0];
      auditFileName.textContent = file.name;
      auditFileSize.textContent = formatFileSize(file.size);
    }

    // 重置进度步骤
    const stepUpload = document.getElementById('step-upload');
    const stepProcessing = document.getElementById('step-processing');
    const stepComplete = document.getElementById('step-complete');

    if (stepUpload && stepProcessing && stepComplete) {
      stepUpload.classList.add('active');
      stepUpload.querySelector('.step-status').textContent = '处理中...';

      stepProcessing.classList.remove('active', 'completed');
      stepProcessing.querySelector('.step-status').textContent = '等待中...';

      stepComplete.classList.remove('active', 'completed');
      stepComplete.querySelector('.step-status').textContent = '等待中...';
    }

    // 重置进度条
    updateProgress(0);
  }
}

function hideProgressModal() {
  const progressModal = document.getElementById('auditProgressModal');
  if (progressModal) {
    progressModal.classList.add('hidden');
  }
}

function updateProgress(percent) {
  const progressBar = document.getElementById('auditProgressBar');
  if (progressBar) {
    progressBar.style.width = `${percent}%`;

    // 更新步骤状态
    if (percent >= 0 && percent < 30) {
      // 文件上传阶段
      updateStepStatus('step-upload', '处理中...', 'active');
    } else if (percent >= 30 && percent < 70) {
      // AI分析阶段
      updateStepStatus('step-upload', '完成', 'completed');
      updateStepStatus('step-processing', '处理中...', 'active');
    } else if (percent >= 70) {
      // 完成阶段
      updateStepStatus('step-upload', '完成', 'completed');
      updateStepStatus('step-processing', '完成', 'completed');
      updateStepStatus('step-complete', '完成', 'active completed');
    }
  }
}

function updateStepStatus(stepId, statusText, className) {
  const step = document.getElementById(stepId);
  if (step) {
    const statusElement = step.querySelector('.step-status');
    if (statusElement) {
      statusElement.textContent = statusText;
    }

    // 添加类名
    if (className) {
      const classNames = className.split(' ');
      classNames.forEach(cls => {
        step.classList.add(cls);
      });
    }
  }
}

// 显示审核报告
function formatAuditReport(report) {
  if (!report || report.trim() === '') {
    console.error('审核报告内容为空');
    return '<p>未能生成审核报告，请重试。</p>';
  }

  try {
    // 提取结论部分
    const conclusionRegex = /(?:结论|总结|审核结论|评估结论)[：:]\s*([\s\S]*?)(?=\n\n|$)/i;
    const conclusionMatch = report.match(conclusionRegex);
    let conclusion = conclusionMatch ? conclusionMatch[1].trim() : '';

    // 从结论中确定状态
    let status = 'review';
    if (conclusion.includes('符合') || conclusion.includes('通过') || conclusion.includes('批准')) {
      status = 'pass';
    } else if (conclusion.includes('不符合') || conclusion.includes('不建议') || conclusion.includes('拒绝')) {
      status = 'fail';
    }

    // 提取政策分析
    const policyRegex = /(?:政策[分析匹配]|政策符合性分析)[：:]\s*([\s\S]*?)(?=\n\n|$)/i;
    const policyMatch = report.match(policyRegex);
    let policyAnalysis = policyMatch ? policyMatch[1].trim() : '';

    // 提取效益分析
    const benefitsRegex = /(?:效益分析|环境效益|经济效益|社会效益)[：:]\s*([\s\S]*?)(?=\n\n|$)/i;
    const benefitsMatch = report.match(benefitsRegex);
    let benefits = benefitsMatch ? benefitsMatch[1].trim() : '';

    // 提取风险分析
    const risksRegex = /(?:风险分析|风险评估|主要风险)[：:]\s*([\s\S]*?)(?=\n\n|$)/i;
    const risksMatch = report.match(risksRegex);
    let risks = risksMatch ? risksMatch[1].trim() : '';

    // 提取改进建议
    const suggestionsRegex = /(?:改进建议|建议|优化方向)[：:]\s*([\s\S]*?)(?=\n\n|$)/i;
    const suggestionsMatch = report.match(suggestionsRegex);
    let suggestions = suggestionsMatch ? suggestionsMatch[1].trim() : '';

    // 提取政策参考
    const referencesRegex = /(?:政策参考|参考政策|相关政策)[：:]\s*([\s\S]*?)(?=\n\n|$)/i;
    const referencesMatch = report.match(referencesRegex);
    let references = referencesMatch ? referencesMatch[1].trim() : '';

    // 如果没有匹配到任何部分，提取关键句子
    if (!conclusion && !policyAnalysis && !benefits && !risks && !suggestions && !references) {
      const sentences = report.split(/[。！？.!?]/g).filter(s => s.trim().length > 10);
      const keyPoints = sentences.slice(0, Math.min(5, sentences.length));
      conclusion = keyPoints.join('。') + '。';
    }

    // 构建HTML - 单层结构
    let html = '<div class="audit-report-flat">';

    // 状态标签
    html += `<span class="conclusion-status status-${status}">${status === 'pass' ? '通过' : (status === 'fail' ? '不通过' : '需进一步审核')}</span>`;

    // 结论部分
    if (conclusion) {
      html += `<h3><i class="fas fa-gavel"></i> 审核结论</h3>
              <p>${conclusion}</p>`;
    }

    // 政策分析
    if (policyAnalysis) {
      const policyItems = extractListItems(policyAnalysis);
      html += `<h3><i class="fas fa-balance-scale"></i> 政策符合性分析</h3>
              ${policyItems}`;
    }

    // 效益分析
    if (benefits) {
      const benefitItems = extractListItems(benefits);
      html += `<h3><i class="fas fa-leaf"></i> 环境效益分析</h3>
              ${benefitItems}`;
    }

    // 风险分析
    if (risks) {
      const riskItems = extractListItems(risks);
      html += `<h3><i class="fas fa-exclamation-triangle"></i> 风险评估</h3>
              ${riskItems}`;
    }

    // 改进建议
    if (suggestions) {
      const suggestionItems = extractListItems(suggestions);
      html += `<h3><i class="fas fa-lightbulb"></i> 改进建议</h3>
              ${suggestionItems}`;
    }

    // 政策参考
    if (references) {
      const referenceItems = extractListItems(references);
      html += `<h3><i class="fas fa-book"></i> 政策参考</h3>
              ${referenceItems}`;
    }

    html += '</div>';

    return html;
  } catch (error) {
    console.error('格式化审核报告时出错:', error);
    return '<p>处理审核报告时出错，请重试。</p>';
  }
}

// 从文本中提取列表项
function extractListItems(text) {
  if (!text) return '';

  // 检查是否已经有序号或项目符号
  const hasBullets = /^[•\-\*\d+\.\s]+/m.test(text);

  if (hasBullets) {
    // 已有序号，处理换行
    const items = text.split('\n').filter(line => line.trim());
    return items.map(item => `<div class="list-item"><span class="list-bullet">•</span>${item.replace(/^[•\-\*\d+\.\s]+/, '')}</div>`).join('');
  } else {
    // 将文本分成句子
    const sentences = text.split(/[。！？.!?]/).filter(s => s.trim());
    return sentences.map(sentence => `<div class="list-item"><span class="list-bullet">•</span>${sentence.trim()}</div>`).join('');
  }
}

function showReport(report) {
  const formattedReport = formatAuditReport(report);
  showReviewResult(formattedReport);
}

// 显示审核结果
function showReviewResult(resultHtml) {
  const reviewResult = document.getElementById('review-result');
  const resultContent = document.getElementById('result-content');
  const noReviewYet = document.getElementById('no-review-yet');

  if (reviewResult && resultContent) {
    resultContent.innerHTML = resultHtml;
    reviewResult.classList.remove('hidden');

    // 隐藏空状态提示
    if (noReviewYet) {
      noReviewYet.style.display = 'none';
    }

    // 切换到审核结果标签
    const tabButtons = document.querySelectorAll('.tab-btn');
    tabButtons.forEach(button => {
      if (button.getAttribute('data-tab') === 'review-tab') {
        button.click();
      }
    });
  }
}

document.addEventListener('DOMContentLoaded', function () {
  // 文件上传相关
  const fileInput = document.getElementById('file-input');
  const uploadArea = document.getElementById('upload-area');
  const fileDetails = document.getElementById('file-details');
  const fileName = document.getElementById('file-name');
  const fileSize = document.getElementById('file-size');
  const uploadBtn = document.getElementById('upload-btn');
  const reviewResult = document.getElementById('review-result');
  const resultContent = document.getElementById('result-content');

  // 聊天相关
  const chatBox = document.getElementById('chat-box');
  const messageInput = document.getElementById('message-input');
  const sendBtn = document.getElementById('send-btn');

  // 标签页切换
  const tabButtons = document.querySelectorAll('.tab-btn');
  const tabContents = document.querySelectorAll('.tab-content');

  tabButtons.forEach(button => {
    button.addEventListener('click', function () {
      // 移除所有激活状态
      tabButtons.forEach(btn => btn.classList.remove('active'));
      tabContents.forEach(content => content.classList.remove('active'));

      // 添加当前激活状态
      this.classList.add('active');
      const tabId = this.getAttribute('data-tab');
      document.getElementById(tabId).classList.add('active');
    });
  });

  // 询问更多建议按钮
  const askMoreBtn = document.getElementById('ask-more-btn');
  if (askMoreBtn) {
    askMoreBtn.addEventListener('click', function () {
      // 切换到聊天标签
      tabButtons.forEach(btn => {
        if (btn.getAttribute('data-tab') === 'chat-tab') {
          btn.click();
        }
      });

      // 预填充消息
      const messageInput = document.getElementById('message-input');
      if (messageInput) {
        messageInput.value = "请针对刚才的审核结果给我一些具体建议";
        messageInput.focus();
      }
    });
  }

  // 导出报告按钮
  const exportBtn = document.getElementById('export-btn');
  if (exportBtn) {
    exportBtn.addEventListener('click', async function () {
      try {
        const resultContent = document.getElementById('result-content');
        if (!resultContent.textContent) {
          alert('没有可导出的报告内容');
          return;
        }

        // 显示加载状态
        const exportBtn = this;
        const originalText = exportBtn.innerHTML;
        exportBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 正在生成PDF...';
        exportBtn.disabled = true;

        // 发送请求生成PDF
        const response = await fetch('http://127.0.0.1:5000/export_report', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            report_content: resultContent.textContent
          })
        });

        if (response.ok) {
          // 获取blob数据
          const blob = await response.blob();
          // 创建下载链接
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `绿色贷款审核报告_${new Date().toISOString().slice(0, 19).replace(/[-:]/g, '')}.pdf`;
          document.body.appendChild(a);
          a.click();
          window.URL.revokeObjectURL(url);
          document.body.removeChild(a);
        } else {
          throw new Error('PDF生成失败');
        }
      } catch (error) {
        console.error('导出报告失败:', error);
        alert('导出报告失败，请稍后重试');
      } finally {
        // 恢复按钮状态
        const exportBtn = document.getElementById('export-btn');
        exportBtn.innerHTML = '<i class="fas fa-download"></i> 导出报告';
        exportBtn.disabled = false;
      }
    });
  }

  // 显示/隐藏初始状态
  function updateReviewResultVisibility() {
    const reviewResult = document.getElementById('review-result');
    const noReviewYet = document.getElementById('no-review-yet');

    if (reviewResult && noReviewYet) {
      if (reviewResult.classList.contains('hidden')) {
        noReviewYet.style.display = 'flex';
      } else {
        noReviewYet.style.display = 'none';
      }
    }
  }

  // 初始化时检查状态
  updateReviewResultVisibility();

  // 在审核结果显示时，同时更新空状态提示
  const originalShowReviewResult = showReviewResult;
  if (typeof showReviewResult === 'function') {
    window.showReviewResult = function () {
      originalShowReviewResult.apply(this, arguments);
      updateReviewResultVisibility();
    };
  }

  // 处理文件拖放
  uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.style.borderColor = '#2ecc71';
    uploadArea.style.backgroundColor = '#f8f9fa';
  });

  uploadArea.addEventListener('dragleave', (e) => {
    e.preventDefault();
    uploadArea.style.borderColor = '#3498db';
    uploadArea.style.backgroundColor = '#ffffff';
  });

  uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.style.borderColor = '#3498db';
    uploadArea.style.backgroundColor = '#ffffff';

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFile(files[0]);
    }
  });

  // 处理文件选择
  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      handleFile(e.target.files[0]);
    }
  });

  // 处理文件
  function handleFile(file) {
    // 检查文件类型
    const validTypes = ['.doc', '.docx', '.pdf', '.txt'];
    const fileExtension = '.' + file.name.split('.').pop().toLowerCase();

    if (!validTypes.includes(fileExtension)) {
      alert('不支持的文件类型！请上传 .doc, .docx, .pdf, 或 .txt 格式的文件。');
      return;
    }

    // 显示文件信息
    fileName.textContent = file.name;
    fileSize.textContent = formatFileSize(file.size);
    fileDetails.style.display = 'block';
  }

  // 聊天发送按钮点击事件
  sendBtn.addEventListener('click', sendMessage);

  // 按Enter键发送消息
  messageInput.addEventListener('keypress', function (e) {
    if (e.key === 'Enter') {
      sendMessage();
    }
  });

  function sendMessage() {
    const message = messageInput.value.trim();
    if (!message) return;

    // 添加用户消息到聊天框
    addChatMessage(message, 'user');

    // 清空输入框
    messageInput.value = '';

    // 显示正在输入状态
    const typingIndicator = addChatMessage('正在输入...', 'bot');
    typingIndicator.classList.add('typing');

    // 使用fetch发送消息到后端
    fetch('/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Origin': 'http://127.0.0.1:5000',
        'Access-Control-Allow-Credentials': 'true'
      },
      credentials: 'include',
      body: JSON.stringify({
        message: message,
        timestamp: new Date().getTime()
      })
    })
      .then(response => {
        if (!response.ok) {
          if (response.status === 500) {
            throw new Error('服务器内部错误，请稍后重试');
          } else if (response.status === 401) {
            throw new Error('API 认证失败，请检查 API 密钥');
          } else {
            throw new Error(`请求失败: ${response.status}`);
          }
        }
        return response.json();
      })
      .then(data => {
        // 移除正在输入状态
        typingIndicator.remove();

        if (data.error) {
          console.error('API错误:', data.error);
          addChatMessage(`错误: ${data.error}`, 'bot');
        } else if (data.response) {
          addChatMessage(data.response, 'bot');
        } else {
          addChatMessage('抱歉，出现了一些问题，请稍后重试', 'bot');
        }
      })
      .catch(error => {
        console.error('聊天失败:', error);
        typingIndicator.remove();
        addChatMessage(`发生错误: ${error.message}`, 'bot');
      });
  }

  function addChatMessage(content, type) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${type}-message`;

    // 添加头像
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';

    if (type === 'user') {
      avatar.innerHTML = '<i class="fas fa-user"></i>';
    } else {
      avatar.innerHTML = '<i class="fas fa-robot"></i>';
    }

    // 添加消息内容
    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';

    // 处理消息内容
    if (type === 'bot' && content !== '正在输入...') {
      try {
        const formattedContent = formatStructuredContent(content);
        messageContent.innerHTML = formattedContent;
      } catch (e) {
        console.error('格式化消息内容出错:', e);
        messageContent.innerHTML = `<p>${content}</p>`;
      }
    } else {
      messageContent.innerHTML = `<p>${content}</p>`;
    }

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(messageContent);

    chatBox.appendChild(messageDiv);
    // 滚动到底部
    chatBox.scrollTop = chatBox.scrollHeight;

    return messageDiv;
  }

  function formatStructuredContent(content) {
    // 检测是否有内容
    if (!content) return '';

    // 处理段落，将连续的多个换行符替换为段落标签
    content = content.replace(/\n{2,}/g, '</p><p>');

    // 处理单行换行
    content = content.replace(/\n/g, '<br>');

    // 处理段落标题
    content = content.replace(/([一二三四五六七八九十]+[、：:．.])([^<>\n]+)/g, '<h3 class="chat-subtitle">$1$2</h3>');
    content = content.replace(/(第[一二三四五六七八九十]+[章节]|[\d]+[\.\s、]+)([^<>\n]+)/g, '<h3 class="chat-subtitle">$1$2</h3>');

    // 处理标题和子标题
    content = content.replace(/(政策匹配分析|环境效益评估|风险评估|审核结论|建议|支持政策依据|项目概述)[:：]/g,
      '<h3 class="chat-title">$1：</h3><p>');

    // 处理序号列表（例如：1. 内容）
    content = content.replace(/(\d+\.|\d+、|\(\d+\)|\d+\))\s*([^\n<]+)(?=\n|<|$)/g,
      '<div class="list-item"><span class="list-number">$1</span> $2</div>');

    // 处理短横线列表
    content = content.replace(/[-•]\s+([^\n]+)/g,
      '<div class="list-item"><span class="list-bullet">•</span> $1</div>');

    // 处理政策引用
    content = content.replace(/《([^》]+)》/g, '<span class="policy-reference">《$1》</span>');

    // 处理重要提示
    content = content.replace(/【([^】]+)】/g, '<span class="important-note">【$1】</span>');

    // 处理数字和单位
    content = content.replace(/(\d+)([吨万元度%℃])/g, '<span class="number">$1</span>$2');

    // 包装在段落中
    if (!content.startsWith('<h3') && !content.startsWith('<p>')) {
      content = '<p>' + content;
    }
    if (!content.endsWith('</p>')) {
      content += '</p>';
    }

    // 确保段落封闭正确
    const openCount = (content.match(/<p>/g) || []).length;
    const closeCount = (content.match(/<\/p>/g) || []).length;
    if (openCount > closeCount) {
      content += '</p>'.repeat(openCount - closeCount);
    }

    return content;
  }

  function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;

    document.body.appendChild(notification);

    // 3秒后自动移除通知
    setTimeout(() => {
      notification.remove();
    }, 3000);
  }

  // 模态框关闭按钮
  const closeAuditModalBtn = document.getElementById('closeAuditModal');
  const cancelAuditBtn = document.getElementById('cancelAudit');

  if (closeAuditModalBtn) {
    closeAuditModalBtn.addEventListener('click', hideProgressModal);
  }

  if (cancelAuditBtn) {
    cancelAuditBtn.addEventListener('click', hideProgressModal);
  }
});