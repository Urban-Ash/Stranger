// 简单前端 i18n 模块：管理语言、字典与翻译应用
const I18N_STORAGE_KEY = 'lang';

const dictionaries = {
  zh: {
    app_title: 'Stranger',
    subtitle: 'OSINT信息检索平台',
    theme_toggle_aria: '切换主题',
    theme_toggle_title: '切换主题',
    search_placeholder: '输入关键词...',
    searching: '搜索中...',
    loading: '加载中...',
    add_title: '添加新数据',
    edit_title: '编辑数据',
    add_name: '姓名',
    add_id_card: '身份证号',
    add_phones: '手机号',
    add_qqs: 'QQ号',
    add_weibo_uid: '微博UID',
    add_email: '邮箱',
    add_gender: '性别',
    add_gender_male: '男',
    add_gender_female: '女',
    add_birth_date: '出生日期',
    add_location: '地址',
    add_company: '公司',
    add_position: '职位',
    add_industry: '行业',
    add_cancel: '取消',
    add_submit: '添加数据',
    back_to_home: '返回',
    card_counter: '{current} / {total}',
    lang_toggle_title: '切换语言',
    lang_zh: '中文',
    lang_zh_tw: '繁體中文',
    lang_en: 'English',
    lang_ja: '日本語',
    lang_menu_aria: '可选择语言',
    unknown: '未知',
    error_title: '查询失败',
    service_unavailable_title: '服务暂不可用',
    service_unavailable_desc: '后端数据库当前不可用或较慢，请稍后重试。',
    retry: '重试',
    network_error_title: '网络错误',
    network_error_desc: '网络连接异常或请求被阻止，请检查网络后重试。',
    add_success: '添加成功',
    add_failed_prefix: '添加失败：',
    edit_success: '修改保存成功',
    edit_failed_prefix: '保存失败：',
    delete_success: '记录删除成功',
    delete_failed: '删除失败，请重试',
    delete_record: '删除记录',
    edit_submit: '保存修改',
    edit_custom_hint: '可以添加任何其他相关信息，如备注、特殊标记等',
    edit_data_sources_hint: '只会添加新的数据来源，不会替换现有数据',
    existing_sources_label: '现有数据来源：',
    no_results_title: '未找到匹配的结果',
    no_results_desc: '请尝试使用不同的关键词，如QQ号、手机号、身份证号等',
    source_detail_title: '来源详情',
    source_no_records_title: '无匹配记录',
    source_no_records_desc: '该数据源未匹配到相关记录',
    ai_assessment_title: 'AI置信度评估',
    ai_assessment_report_title: 'AI置信度评估报告',
    ai_no_data: '暂无评估数据',
    ai_click_to_assess: '请点击AI按钮进行评估',
    field_ai_confidence: '置信度',
    field_id_card: '身份证号',
    field_phones: '手机号',
    field_phone: '手机号',
    field_emails: '邮箱',
    field_email: '邮箱',
    field_qqs: 'QQ号',
    field_qq: 'QQ号',
    field_weibo_uids: '微博UID',
    field_weibo_uid: '微博UID',
    field_name: '姓名',
    field_gender: '性别',
    field_birth_date: '出生日期',
    field_native_place: '籍贯',
    field_location: '地址',
    field_address: '地址',
    field_company: '公司',
    field_position: '职位',
    field_industry: '行业',
    field_custom_info: '其他信息',
    field_metadata: '元数据',
    field_created_at: '创建时间',
    field_updated_at: '更新时间',
    field_data_sources: '数据来源',
    field_formatted_data_sources: '数据来源',
    field_source: '来源',
    field_captured_at: '捕获时间',
    field_relative_name: '直系亲属姓名',
    field_relative_phone: '直系亲属手机号',
    field_spouse_name: '配偶姓名',
    field_spouse_phone: '配偶手机号',
    field_relationship: '关系',
    field_related_to: '关联对象'
    ,
    // 交互芯片与查询/校验流程文案
    title_query_carrier: '查询归属地',
    title_query_qq: '查询QQ信息',
    title_query_weibo_uid: '查询微博UID信息',
    title_recognize_email: '识别邮箱中的手机号或QQ',
    title_validate_id_card: '校验身份证号',
    phone_carrier_query_title: '手机号归属地',
    qq_info_query_title: 'QQ信息',
    weibo_uid_query_title: '微博UID信息',
    email_recognition_title: '邮箱识别',
    email_recognition_phone_title: '邮箱识别：手机号归属地',
    email_recognition_qq_title: '邮箱识别：QQ信息',
    email_recognition_no_hit: '未识别出手机号或QQ',
    querying: '查询中...',
    validating: '校验中...',
    // 无结果建议面板
    suggest_leads: '建议线索',
    suggest_leads_open: '打开建议线索',
    suggest_leads_intro: '可尝试：',
    suggest_leads_item_1: '使用更完整的关键词（如手机号、QQ、身份证号）',
    suggest_leads_item_2: '尝试不同字段组合，如姓名 + 公司',
    suggest_leads_item_3: '检查是否存在别名或曾用名',
    suggest_leads_item_4: '稍后重试或更换数据源',
    show_all: '展开显示全部',
    // AI评估与复制提示
    ai_assess_done: '评估完成，已更新置信度',
    ai_assess_error_prefix: '评估错误：',
    ai_assessment_report_title_fmt: 'AI置信度评估（{level}，{percent}%）',
    query_failed_title: '查询失败',
    invalid_result: '无效的结果',
    missing_id_card_assess_unavailable: '缺少身份证号，无法评估',
    qq_info_empty_title: '未返回QQ信息',
    weibo_info_empty_title: '未返回微博信息',
    validation_no_data_title: '未返回校验信息',
    phone_carrier_no_data_title: '未提取到归属地信息',
    copy: '复制',
    copied_to_clipboard: '已复制到剪贴板',
    copy_failed: '复制失败',
    copy_failed_prefix: '复制失败：',
    copy_failed_try_manual: '复制失败，请手动选择复制',
    copy_failed_invalid: '复制失败：无效的结果',
    // 登录页
    login_title: '登录 Stranger',
    login_username: '用户名',
    login_password: '密码',
    login_submit: '登录',
    login_error_invalid_credentials: '用户名或密码错误'
  },
  en: {
    app_title: 'Stranger',
    subtitle: 'OSINT information retrieval platform',
    theme_toggle_aria: 'Toggle theme',
    theme_toggle_title: 'Toggle theme',
    search_placeholder: 'Type keywords...',
    searching: 'Searching...',
    loading: 'Loading...',
    add_title: 'Add New Data',
    edit_title: 'Edit Data',
    add_name: 'Name',
    add_id_card: 'ID Card',
    add_phones: 'Phone',
    add_qqs: 'QQ',
    add_weibo_uid: 'Weibo UID',
    add_email: 'Email',
    add_gender: 'Gender',
    add_gender_male: 'Male',
    add_gender_female: 'Female',
    add_birth_date: 'Birth Date',
    add_location: 'Address',
    add_company: 'Company',
    add_position: 'Position',
    add_industry: 'Industry',
    add_cancel: 'Cancel',
    add_submit: 'Submit',
    back_to_home: 'Back',
    card_counter: '{current} / {total}',
    lang_toggle_title: 'Switch Language',
    lang_zh: '中文',
    lang_zh_tw: '繁體中文',
    lang_en: 'EN',
    lang_ja: '日本語',
    lang_menu_aria: 'Available languages',
    unknown: 'Unknown',
    error_title: 'Search Failed',
    service_unavailable_title: 'Service Unavailable',
    service_unavailable_desc: 'Backend database is unavailable or slow. Please try again later.',
    retry: 'Retry',
    network_error_title: 'Network Error',
    network_error_desc: 'Network connection issue or request blocked. Please check and retry.',
    add_success: 'Added successfully',
    add_failed_prefix: 'Add failed: ',
    edit_success: 'Saved successfully',
    edit_failed_prefix: 'Save failed: ',
    delete_success: 'Record deleted successfully',
    delete_failed: 'Delete failed, please retry',
    delete_record: 'Delete Record',
    edit_submit: 'Save Changes',
    edit_custom_hint: 'Add any other relevant info, e.g., notes or special tags',
    edit_data_sources_hint: 'Only adds new data sources, does not replace existing ones',
    existing_sources_label: 'Existing data sources:',
    no_results_title: 'No results found',
    no_results_desc: 'Try different keywords such as QQ number, phone, or ID card.',
    source_detail_title: 'Source Detail',
    source_no_records_title: 'No matching records',
    source_no_records_desc: 'This data source did not match any related records.',
    ai_assessment_title: 'AI Confidence Assessment',
    ai_assessment_report_title: 'AI Confidence Assessment Report',
    ai_no_data: 'No assessment data',
    ai_click_to_assess: 'Click the AI button to assess',
    field_ai_confidence: 'Confidence',
    field_id_card: 'ID Card',
    field_phones: 'Phone',
    field_phone: 'Phone',
    field_emails: 'Email',
    field_email: 'Email',
    field_qqs: 'QQ',
    field_qq: 'QQ',
    field_weibo_uids: 'Weibo UID',
    field_weibo_uid: 'Weibo UID',
    field_name: 'Name',
    field_gender: 'Gender',
    field_birth_date: 'Birth Date',
    field_native_place: 'Native Place',
    field_location: 'Address',
    field_address: 'Address',
    field_company: 'Company',
    field_position: 'Position',
    field_industry: 'Industry',
    field_custom_info: 'Custom Info',
    field_metadata: 'Metadata',
    field_created_at: 'Created At',
    field_updated_at: 'Updated At',
    field_data_sources: 'Data Sources',
    field_formatted_data_sources: 'Data Sources',
    field_source: 'Source',
    field_captured_at: 'Captured At',
    field_relative_name: 'Relative Name',
    field_relative_phone: 'Relative Phone',
    field_spouse_name: 'Spouse Name',
    field_spouse_phone: 'Spouse Phone',
    field_relationship: 'Relationship',
    field_related_to: 'Related To'
    ,
    // Chip titles and query/validation flow texts
    title_query_carrier: 'Query carrier/location',
    title_query_qq: 'Query QQ info',
    title_query_weibo_uid: 'Query Weibo UID info',
    title_recognize_email: 'Recognize phone/QQ from email',
    title_validate_id_card: 'Validate ID card',
    phone_carrier_query_title: 'Phone Carrier & Location',
    qq_info_query_title: 'QQ Info',
    weibo_uid_query_title: 'Weibo UID Info',
    email_recognition_title: 'Email Recognition',
    email_recognition_phone_title: 'Email Recognition: Phone Carrier & Location',
    email_recognition_qq_title: 'Email Recognition: QQ Info',
    email_recognition_no_hit: 'No phone or QQ recognized',
    querying: 'Querying...',
    validating: 'Validating...',
    // No-results suggestions panel
    suggest_leads: 'Suggested Leads',
    suggest_leads_open: 'Open Suggested Leads',
    suggest_leads_intro: 'Try the following:',
    suggest_leads_item_1: 'Use more complete keywords (phone, QQ, ID card)',
    suggest_leads_item_2: 'Try combining fields, e.g., name + company',
    suggest_leads_item_3: 'Check for aliases or former names',
    suggest_leads_item_4: 'Retry later or switch data sources',
    show_all: 'Show all',
    // AI assessment and copy prompts
    ai_assess_done: 'Assessment complete, confidence updated',
    ai_assess_error_prefix: 'Assessment error: ',
    ai_assessment_report_title_fmt: 'AI Confidence Assessment ({level}, {percent}%)',
    query_failed_title: 'Query Failed',
    invalid_result: 'Invalid result',
    missing_id_card_assess_unavailable: 'Missing ID card; cannot assess',
    qq_info_empty_title: 'No QQ info returned',
    weibo_info_empty_title: 'No Weibo info returned',
    validation_no_data_title: 'No validation info returned',
    phone_carrier_no_data_title: 'No carrier info extracted',
    copy: 'Copy',
    copied_to_clipboard: 'Copied to clipboard',
    copy_failed: 'Copy failed',
    copy_failed_prefix: 'Copy failed: ',
    copy_failed_try_manual: 'Copy failed, please copy manually',
    copy_failed_invalid: 'Copy failed: invalid result',
    // Login page
    login_title: 'Login to Stranger',
    login_username: 'Username',
    login_password: 'Password',
    login_submit: 'Login',
    login_error_invalid_credentials: 'Invalid username or password'
  },
  'zh-TW': {
    app_title: 'Stranger',
    subtitle: 'OSINT資訊檢索平台',
    theme_toggle_aria: '切換主題',
    theme_toggle_title: '切換主題',
    search_placeholder: '輸入關鍵詞...',
    searching: '搜索中...',
    loading: '加載中...',
    add_title: '添加新資料',
    edit_title: '編輯資料',
    add_name: '姓名',
    add_id_card: '身份證號',
    add_phones: '手機號',
    add_qqs: 'QQ號',
    add_weibo_uid: '微博 UID',
    add_email: '電子郵件',
    add_gender: '性別',
    add_gender_male: '男',
    add_gender_female: '女',
    add_birth_date: '出生日期',
    add_location: '地址',
    add_company: '公司',
    add_position: '職位',
    add_industry: '行業',
    add_cancel: '取消',
    add_submit: '添加資料',
    back_to_home: '返回',
    card_counter: '{current} / {total}',
    lang_toggle_title: '切換語言',
    lang_zh: '中文',
    lang_zh_tw: '繁體中文',
    lang_en: 'EN',
    lang_ja: '日本語',
    lang_menu_aria: '可選擇語言',
    unknown: '未知',
    error_title: '查詢失敗',
    service_unavailable_title: '服務暫不可用',
    service_unavailable_desc: '後端資料庫目前不可用或較慢，請稍後再試。',
    retry: '重試',
    network_error_title: '網路錯誤',
    network_error_desc: '網路連線異常或請求被阻擋，請檢查後重試。',
    add_success: '添加成功',
    add_failed_prefix: '添加失敗：',
    edit_success: '修改保存成功',
    edit_failed_prefix: '保存失敗：',
    delete_success: '記錄刪除成功',
    delete_failed: '刪除失敗，請重試',
    delete_record: '刪除記錄',
    edit_submit: '保存變更',
    edit_custom_hint: '可添加其他相關資訊，如備註、特殊標記等',
    edit_data_sources_hint: '僅會添加新的資料來源，不會替換現有資料',
    existing_sources_label: '現有資料來源：',
    no_results_title: '未找到匹配的結果',
    no_results_desc: '請嘗試不同的關鍵詞，如 QQ 號、手機號、身份證號等',
    source_detail_title: '來源詳情',
    source_no_records_title: '無匹配記錄',
    source_no_records_desc: '該數據源未匹配到相關記錄',
    ai_assessment_title: 'AI 置信度評估',
    ai_assessment_report_title: 'AI 置信度評估報告',
    ai_no_data: '暫無評估資料',
    ai_click_to_assess: '請點擊 AI 按鈕進行評估',
    field_ai_confidence: '置信度',
    field_id_card: '身份證號',
    field_phones: '手機號',
    field_phone: '手機號',
    field_emails: '電子郵件',
    field_email: '電子郵件',
    field_qqs: 'QQ號',
    field_qq: 'QQ號',
    field_weibo_uids: '微博 UID',
    field_weibo_uid: '微博 UID',
    field_name: '姓名',
    field_gender: '性別',
    field_birth_date: '出生日期',
    field_native_place: '籍貫',
    field_location: '地址',
    field_address: '地址',
    field_company: '公司',
    field_position: '職位',
    field_industry: '行業',
    field_custom_info: '其他資訊',
    field_metadata: '元資料',
    field_created_at: '建立時間',
    field_updated_at: '更新時間',
    field_data_sources: '資料來源',
    field_formatted_data_sources: '資料來源',
    field_source: '來源',
    field_captured_at: '捕獲時間',
    field_relative_name: '直系親屬姓名',
    field_relative_phone: '直系親屬手機號',
    field_spouse_name: '配偶姓名',
    field_spouse_phone: '配偶手機號',
    field_relationship: '關係',
    field_related_to: '關聯對象'
    ,
    // 互動標籤與查詢/校驗流程文案
    title_query_carrier: '查詢歸屬地',
    title_query_qq: '查詢 QQ 資訊',
    title_query_weibo_uid: '查詢 Weibo UID 資訊',
    title_recognize_email: '辨識郵箱中的手機或 QQ',
    title_validate_id_card: '校驗身分證號',
    phone_carrier_query_title: '手機號歸屬地',
    qq_info_query_title: 'QQ 資訊',
    weibo_uid_query_title: 'Weibo UID 資訊',
    email_recognition_title: '郵箱辨識',
    email_recognition_phone_title: '郵箱辨識：手機號歸屬地',
    email_recognition_qq_title: '郵箱辨識：QQ 資訊',
    email_recognition_no_hit: '未辨識出手機或 QQ',
    querying: '查詢中...',
    validating: '校驗中...',
    // 無結果建議面板
    suggest_leads: '建議線索',
    suggest_leads_open: '打開建議線索',
    suggest_leads_intro: '可嘗試：',
    suggest_leads_item_1: '使用更完整的關鍵詞（如手機、QQ、身分證）',
    suggest_leads_item_2: '嘗試不同欄位組合，如姓名 + 公司',
    suggest_leads_item_3: '檢查是否存在別名或曾用名',
    suggest_leads_item_4: '稍後重試或更換資料來源',
    show_all: '展開顯示全部',
    // AI 評估與複製提示
    ai_assess_done: '評估完成，已更新置信度',
    ai_assess_error_prefix: '評估錯誤：',
    ai_assessment_report_title_fmt: 'AI 置信度評估（{level}，{percent}%）',
    query_failed_title: '查詢失敗',
    invalid_result: '無效的結果',
    missing_id_card_assess_unavailable: '缺少身分證號，無法評估',
    qq_info_empty_title: '未返回 QQ 資訊',
    weibo_info_empty_title: '未返回 Weibo 資訊',
    validation_no_data_title: '未返回校驗資訊',
    phone_carrier_no_data_title: '未提取到歸屬地資訊',
    copy: '複製',
    copied_to_clipboard: '已複製到剪貼簿',
    copy_failed: '複製失敗',
    copy_failed_prefix: '複製失敗：',
    copy_failed_try_manual: '複製失敗，請手動選擇複製',
    copy_failed_invalid: '複製失敗：無效的結果',
    // 登入頁
    login_title: '登入 Stranger',
    login_username: '使用者名稱',
    login_password: '密碼',
    login_submit: '登入',
    login_error_invalid_credentials: '使用者名稱或密碼錯誤'
  },
  ja: {
    app_title: 'Stranger',
    subtitle: 'OSINT情報検索プラットフォーム',
    theme_toggle_aria: 'テーマを切り替え',
    theme_toggle_title: 'テーマを切り替え',
    search_placeholder: 'キーワードを入力...',
    searching: '検索中...',
    loading: '読み込み中...',
    add_title: '新規データを追加',
    edit_title: 'データを編集',
    add_name: '氏名',
    add_id_card: '身分証番号',
    add_phones: '電話番号',
    add_qqs: 'QQ番号',
    add_weibo_uid: 'Weibo UID',
    add_email: 'メール',
    add_gender: '性別',
    add_gender_male: '男性',
    add_gender_female: '女性',
    add_birth_date: '生年月日',
    add_location: '住所',
    add_company: '会社',
    add_position: '役職',
    add_industry: '業界',
    add_cancel: 'キャンセル',
    add_submit: '追加',
    back_to_home: '戻る',
    card_counter: '{current} / {total}',
    lang_toggle_title: '言語を切り替え',
    lang_zh: '中文',
    lang_zh_tw: '繁體中文',
    lang_en: 'English',
    lang_ja: '日本語',
    lang_menu_aria: '選択可能な言語',
    unknown: '不明',
    error_title: '検索失敗',
    service_unavailable_title: 'サービスは利用できません',
    service_unavailable_desc: 'バックエンドのデータベースが利用不可または遅延しています。しばらくしてから再試行してください。',
    retry: '再試行',
    network_error_title: 'ネットワークエラー',
    network_error_desc: 'ネットワーク接続の問題、またはリクエストがブロックされました。確認して再試行してください。',
    add_success: '追加に成功しました',
    add_failed_prefix: '追加に失敗: ',
    edit_success: '保存に成功しました',
    edit_failed_prefix: '保存に失敗: ',
    delete_success: '削除に成功しました',
    delete_failed: '削除に失敗しました。再試行してください',
    delete_record: '記録を削除',
    edit_submit: '変更を保存',
    edit_custom_hint: '備考や特別なタグなど、関連情報を追加できます',
    edit_data_sources_hint: '新しいデータソースのみ追加し、既存データは置き換えません',
    existing_sources_label: '既存のデータソース：',
    no_results_title: '一致する結果は見つかりませんでした',
    no_results_desc: 'QQ番号、電話番号、身分証番号など別のキーワードを試してください',
    source_detail_title: 'ソース詳細',
    source_no_records_title: '一致する記録はありません',
    source_no_records_desc: 'このデータソースでは関連記録が見つかりませんでした',
    ai_assessment_title: 'AI信頼度評価',
    ai_assessment_report_title: 'AI信頼度評価レポート',
    ai_no_data: '評価データなし',
    ai_click_to_assess: 'AIボタンをクリックして評価',
    field_ai_confidence: '信頼度',
    field_id_card: '身分証番号',
    field_phones: '電話番号',
    field_phone: '電話番号',
    field_emails: 'メール',
    field_email: 'メール',
    field_qqs: 'QQ',
    field_qq: 'QQ',
    field_weibo_uids: 'Weibo UID',
    field_weibo_uid: 'Weibo UID',
    field_name: '氏名',
    field_gender: '性別',
    field_birth_date: '生年月日',
    field_native_place: '出身地',
    field_location: '住所',
    field_address: '住所',
    field_company: '会社',
    field_position: '役職',
    field_industry: '業界',
    field_custom_info: 'カスタム情報',
    field_metadata: 'メタデータ',
    field_created_at: '作成日時',
    field_updated_at: '更新日時',
    field_data_sources: 'データソース',
    field_formatted_data_sources: 'データソース',
    field_source: 'ソース',
    field_captured_at: '取得日時',
    field_relative_name: '親族氏名',
    field_relative_phone: '親族電話',
    field_spouse_name: '配偶者氏名',
    field_spouse_phone: '配偶者電話',
    field_relationship: '関係',
    field_related_to: '関連対象'
    ,
    // チップタイトルとクエリ/検証フローのテキスト
    title_query_carrier: 'キャリア・所在地を照会',
    title_query_qq: 'QQ情報を照会',
    title_query_weibo_uid: 'Weibo UID情報を照会',
    title_recognize_email: 'メールから電話/QQを識別',
    title_validate_id_card: '身分証番号を検証',
    phone_carrier_query_title: '電話番号のキャリア・所在地',
    qq_info_query_title: 'QQ情報',
    weibo_uid_query_title: 'Weibo UID情報',
    email_recognition_title: 'メール識別',
    email_recognition_phone_title: 'メール識別：電話のキャリア・所在地',
    email_recognition_qq_title: 'メール識別：QQ情報',
    email_recognition_no_hit: '電話番号またはQQを識別できませんでした',
    querying: '検索中...',
    validating: '検証中...',
    // 提案パネル
    suggest_leads: '提案された手掛かり',
    suggest_leads_open: '提案を開く',
    suggest_leads_intro: '次を試してください：',
    suggest_leads_item_1: 'より完全なキーワードを使用（電話、QQ、身分証）',
    suggest_leads_item_2: 'フィールドを組み合わせる（氏名 + 会社）',
    suggest_leads_item_3: '別名や旧名を確認',
    suggest_leads_item_4: '後で再試行またはデータソースを変更',
    show_all: 'すべて表示',
    // AI 評価とコピーのプロンプト
    ai_assess_done: '評価完了、信頼度を更新しました',
    ai_assess_error_prefix: '評価エラー: ',
    ai_assessment_report_title_fmt: 'AI信頼度評価（{level}、{percent}%）',
    query_failed_title: '検索失敗',
    invalid_result: '無効な結果',
    missing_id_card_assess_unavailable: '身分証番号が不足しており、評価できません',
    qq_info_empty_title: 'QQ情報は返されませんでした',
    weibo_info_empty_title: 'Weibo情報は返されませんでした',
    validation_no_data_title: '検証情報は返されませんでした',
    phone_carrier_no_data_title: 'キャリア情報を抽出できませんでした',
    copy: 'コピー',
    copied_to_clipboard: 'クリップボードにコピーしました',
    copy_failed: 'コピーに失敗しました',
    copy_failed_prefix: 'コピー失敗: ',
    copy_failed_try_manual: 'コピーに失敗、手動でコピーしてください',
    copy_failed_invalid: 'コピー失敗：無効な結果',
    // ログインページ
    login_title: 'Stranger にログイン',
    login_username: 'ユーザー名',
    login_password: 'パスワード',
    login_submit: 'ログイン',
    login_error_invalid_credentials: 'ユーザー名またはパスワードが正しくありません'
  }
  ,
  ko: {
    app_title: 'Stranger',
    subtitle: 'OSINT 정보 검색 플랫폼',
    theme_toggle_aria: '테마 전환',
    theme_toggle_title: '테마 전환',
    search_placeholder: '키워드를 입력하세요...',
    searching: '검색 중...',
    loading: '로딩 중...',
    add_title: '데이터 추가',
    edit_title: '데이터 편집',
    add_name: '이름',
    add_id_card: '신분증 번호',
    add_phones: '전화번호',
    add_qqs: 'QQ 번호',
    add_weibo_uid: '웨이보 UID',
    add_email: '이메일',
    add_gender: '성별',
    add_gender_male: '남성',
    add_gender_female: '여성',
    add_birth_date: '생년월일',
    add_location: '주소',
    add_company: '회사',
    add_position: '직책',
    add_industry: '업종',
    add_cancel: '취소',
    add_submit: '제출',
    back_to_home: '돌아가기',
    card_counter: '{current} / {total}',
    lang_toggle_title: '언어 전환',
    lang_zh: '中文',
    lang_zh_tw: '繁體中文',
    lang_en: 'English',
    lang_ja: '日本語',
    lang_menu_aria: '사용 가능한 언어',
    unknown: '알 수 없음',
    error_title: '검색 실패',
    service_unavailable_title: '서비스 이용 불가',
    service_unavailable_desc: '백엔드 데이터베이스가 이용 불가 또는 지연 중입니다. 잠시 후 다시 시도하세요.',
    retry: '다시 시도',
    network_error_title: '네트워크 오류',
    network_error_desc: '네트워크 연결 문제 또는 요청이 차단되었습니다. 확인 후 다시 시도하세요.',
    add_success: '추가 성공',
    add_failed_prefix: '추가 실패: ',
    edit_success: '저장 성공',
    edit_failed_prefix: '저장 실패: ',
    delete_success: '삭제 성공',
    delete_failed: '삭제 실패, 다시 시도하세요',
    delete_record: '기록 삭제',
    edit_submit: '변경 사항 저장',
    edit_custom_hint: '메모나 특별한 태그 등 관련 정보를 추가하세요',
    edit_data_sources_hint: '새 데이터 소스만 추가하며 기존 데이터는 대체하지 않습니다',
    existing_sources_label: '기존 데이터 소스:',
    no_results_title: '결과가 없습니다',
    no_results_desc: 'QQ, 전화번호, 신분증 등 다른 키워드를 시도하세요.',
    source_detail_title: '소스 상세',
    source_no_records_title: '일치하는 기록 없음',
    source_no_records_desc: '이 데이터 소스에서 관련 기록을 찾지 못했습니다',
    ai_assessment_title: 'AI 신뢰도 평가',
    ai_assessment_report_title: 'AI 신뢰도 평가 보고서',
    ai_no_data: '평가 데이터 없음',
    ai_click_to_assess: '평가하려면 AI 버튼을 클릭하세요',
    field_ai_confidence: '신뢰도',
    field_id_card: '신분증 번호',
    field_phones: '전화번호',
    field_phone: '전화번호',
    field_emails: '이메일',
    field_email: '이메일',
    field_qqs: 'QQ',
    field_qq: 'QQ',
    field_weibo_uids: '웨이보 UID',
    field_weibo_uid: '웨이보 UID',
    field_name: '이름',
    field_gender: '성별',
    field_birth_date: '생년월일',
    field_native_place: '출생지',
    field_location: '주소',
    field_address: '주소',
    field_company: '회사',
    field_position: '직책',
    field_industry: '업종',
    field_custom_info: '기타 정보',
    field_metadata: '메타데이터',
    field_created_at: '생성 시각',
    field_updated_at: '업데이트 시각',
    field_data_sources: '데이터 소스',
    field_formatted_data_sources: '데이터 소스',
    field_source: '소스',
    field_captured_at: '수집 시각',
    field_relative_name: '친족 이름',
    field_relative_phone: '친족 전화',
    field_spouse_name: '배우자 이름',
    field_spouse_phone: '배우자 전화',
    field_relationship: '관계',
    field_related_to: '관련 대상'
    ,
    // 칩 제목 및 조회/검증 흐름 문구
    title_query_carrier: '통신사/지역 조회',
    title_query_qq: 'QQ 정보 조회',
    title_query_weibo_uid: '웨이보 UID 정보 조회',
    title_recognize_email: '이메일에서 전화/QQ 추출',
    title_validate_id_card: '신분증 번호 검증',
    phone_carrier_query_title: '전화번호 통신사/지역',
    qq_info_query_title: 'QQ 정보',
    weibo_uid_query_title: '웨이보 UID 정보',
    email_recognition_title: '이메일 인식',
    email_recognition_phone_title: '이메일 인식: 전화 통신사/지역',
    email_recognition_qq_title: '이메일 인식: QQ 정보',
    email_recognition_no_hit: '전화번호 또는 QQ를 인식하지 못했습니다',
    querying: '검색 중...',
    validating: '검증 중...',
    // 제안 패널
    suggest_leads: '추천 단서',
    suggest_leads_open: '추천 단서 열기',
    suggest_leads_intro: '다음 시도:',
    suggest_leads_item_1: '더 완전한 키워드 사용 (전화, QQ, 신분증)',
    suggest_leads_item_2: '필드를 조합 (이름 + 회사)',
    suggest_leads_item_3: '별명이나 이전 이름 확인',
    suggest_leads_item_4: '나중에 재시도하거나 데이터 소스 변경',
    show_all: '모두 보기',
    // AI 평가 및 복사 프롬프트
    ai_assess_done: '평가 완료, 신뢰도 업데이트됨',
    ai_assess_error_prefix: '평가 오류: ',
    ai_assessment_report_title_fmt: 'AI 신뢰도 평가 ({level}, {percent}%)',
    query_failed_title: '검색 실패',
    invalid_result: '잘못된 결과',
    missing_id_card_assess_unavailable: '신분증 번호가 없어 평가할 수 없습니다',
    qq_info_empty_title: 'QQ 정보가 반환되지 않았습니다',
    weibo_info_empty_title: '웨이보 정보가 반환되지 않았습니다',
    validation_no_data_title: '검증 정보가 반환되지 않았습니다',
    phone_carrier_no_data_title: '통신사 정보 추출 실패',
    copy: '복사',
    copied_to_clipboard: '클립보드로 복사됨',
    copy_failed: '복사 실패',
    copy_failed_prefix: '복사 실패: ',
    copy_failed_try_manual: '복사 실패, 수동으로 복사하세요',
    copy_failed_invalid: '복사 실패: 잘못된 결과',
    // 로그인 페이지
    login_title: 'Stranger 로그인',
    login_username: '사용자명',
    login_password: '비밀번호',
    login_submit: '로그인',
    login_error_invalid_credentials: '사용자명 또는 비밀번호가 올바르지 않습니다'
  }
};

function detectLang() {
  const raw = (navigator.languages && navigator.languages[0]) || navigator.language || '';
  const lng = String(raw || '').toLowerCase();
  if (lng.startsWith('zh')) {
    if (lng.includes('hant') || lng.includes('tw') || lng.includes('hk')) return 'zh-TW';
    return 'zh';
  }
  if (lng.startsWith('ja')) return 'ja';
  if (lng.startsWith('ko')) return 'ko';
  if (lng.startsWith('en')) return 'en';
  return 'zh';
}

let currentLang = localStorage.getItem(I18N_STORAGE_KEY) || detectLang();

export function getLang() { return currentLang; }
export function setLang(lang) {
  const allowed = ['zh','zh-TW','en','ja','ko'];
  currentLang = allowed.includes(lang) ? lang : 'zh';
  localStorage.setItem(I18N_STORAGE_KEY, currentLang);
  applyTranslations();
}
export function t(key, vars) {
  const dict = dictionaries[currentLang] || dictionaries.zh;
  let str = dict[key] || key;
  if (vars && typeof vars === 'object') {
    Object.keys(vars).forEach(k => {
      str = str.replace(`{${k}}`, vars[k]);
    });
  }
  return str;
}

export function applyTranslations() {
  // 文档标题
  try {
    document.title = `${t('app_title')} - ${t('subtitle')}`;
  } catch {}
  // 标题与副标题
  const title = document.getElementById('strangerTitle');
  if (title) title.textContent = t('app_title');
  const subtitle = document.querySelector('.subtitle');
  if (subtitle) subtitle.textContent = t('subtitle');
  // 主题按钮标签
  const themeToggle = document.getElementById('themeToggle');
  if (themeToggle) {
    themeToggle.title = t('theme_toggle_title');
    themeToggle.setAttribute('aria-label', t('theme_toggle_aria'));
  }
  // 返回按钮 ARIA
  const backToHome = document.getElementById('backToHome');
  if (backToHome) {
    backToHome.title = t('back_to_home');
    backToHome.setAttribute('aria-label', t('back_to_home'));
  }
  // 语言菜单 ARIA
  const langMenu = document.getElementById('langMenu');
  if (langMenu) {
    langMenu.setAttribute('aria-label', t('lang_menu_aria'));
  }
  // 搜索框占位
  const searchInput = document.getElementById('searchInput');
  if (searchInput) searchInput.placeholder = t('search_placeholder');
  // 结果 loading 文案
  const loadingText = document.querySelector('#loadingIndicator p');
  if (loadingText) loadingText.textContent = t('searching');
  // 添加/编辑模态文案
  const addTitle = document.querySelector('#addModal .modal-header h2');
  if (addTitle) addTitle.textContent = t('add_title');
  const editTitle = document.querySelector('#editModal .modal-header h2');
  if (editTitle) editTitle.textContent = t('edit_title');
  function setLabel(sel, key) {
    const el = document.querySelector(sel);
    if (el) el.textContent = t(key);
  }
  setLabel("label[for='addName']", 'add_name');
  setLabel("label[for='addIdCard']", 'add_id_card');
  setLabel("label[for='addPhones']", 'add_phones');
  setLabel("label[for='addQqs']", 'add_qqs');
  setLabel("label[for='addWeiboUid']", 'add_weibo_uid');
  setLabel("label[for='addEmail']", 'add_email');
  setLabel("label[for='addGender']", 'add_gender');
  // 性别选项
  const genderSel = document.getElementById('addGender');
  if (genderSel && genderSel.options && genderSel.options.length >= 3) {
    genderSel.options[0].textContent = t('add_gender');
    genderSel.options[1].textContent = t('add_gender_male');
    genderSel.options[2].textContent = t('add_gender_female');
  }
  setLabel("label[for='addBirthDate']", 'add_birth_date');
  setLabel("label[for='addLocation']", 'add_location');
  setLabel("label[for='addCompany']", 'add_company');
  setLabel("label[for='addPosition']", 'add_position');
  setLabel("label[for='addIndustry']", 'add_industry');
  // 按钮文案
  const cancelAdd = document.getElementById('cancelAdd');
  if (cancelAdd) cancelAdd.textContent = t('add_cancel');
  const submitAdd = document.querySelector('#addDataForm .submit-btn');
  if (submitAdd) submitAdd.textContent = t('add_submit');

  // 编辑模态标签
  setLabel("label[for='editName']", 'add_name');
  setLabel("label[for='editIdCard']", 'add_id_card');
  setLabel("label[for='editPhones']", 'add_phones');
  setLabel("label[for='editQqs']", 'add_qqs');
  setLabel("label[for='editWeiboUid']", 'add_weibo_uid');
  setLabel("label[for='editEmail']", 'add_email');
  setLabel("label[for='editGender']", 'add_gender');
  const editGenderSel = document.getElementById('editGender');
  if (editGenderSel && editGenderSel.options && editGenderSel.options.length >= 3) {
    editGenderSel.options[0].textContent = t('add_gender');
    editGenderSel.options[1].textContent = t('add_gender_male');
    editGenderSel.options[2].textContent = t('add_gender_female');
  }
  setLabel("label[for='editBirthDate']", 'add_birth_date');
  setLabel("label[for='editLocation']", 'add_location');
  setLabel("label[for='editCompany']", 'add_company');
  setLabel("label[for='editPosition']", 'add_position');
  setLabel("label[for='editIndustry']", 'add_industry');
  setLabel("label[for='editCustomInfo']", 'field_custom_info');
  setLabel("label[for='editDataSources']", 'field_data_sources');
  // 编辑按钮与提示
  const deleteRecordBtn = document.getElementById('deleteRecord');
  if (deleteRecordBtn) deleteRecordBtn.textContent = t('delete_record');
  const cancelEditBtn = document.getElementById('cancelEdit');
  if (cancelEditBtn) cancelEditBtn.textContent = t('add_cancel');
  const submitEditBtn = document.querySelector('#editDataForm .submit-btn');
  if (submitEditBtn) submitEditBtn.textContent = t('edit_submit');
  const editHints = document.querySelectorAll('#editDataForm .form-hint');
  if (editHints && editHints.length >= 1) editHints[0].textContent = t('edit_custom_hint');
  if (editHints && editHints.length >= 2) editHints[1].textContent = t('edit_data_sources_hint');
  const existingSourcesLabel = document.querySelector('#existingSources label');
  if (existingSourcesLabel) existingSourcesLabel.textContent = t('existing_sources_label');
  // 来源详情弹窗标题
  const sourceModalTitle = document.getElementById('sourceModalTitle');
  if (sourceModalTitle) sourceModalTitle.textContent = t('source_detail_title');
  // 登录页文案
  const loginTitle = document.getElementById('login-title');
  if (loginTitle) loginTitle.textContent = t('login_title');
  // 输入框与标签
  const loginUser = document.getElementById('username');
  if (loginUser) loginUser.placeholder = t('login_username');
  const loginPass = document.getElementById('password');
  if (loginPass) loginPass.placeholder = t('login_password');
  const labelUsername = document.getElementById('labelUsername');
  if (labelUsername) labelUsername.textContent = t('login_username');
  const labelPassword = document.getElementById('labelPassword');
  if (labelPassword) labelPassword.textContent = t('login_password');
  const loginSubmit = document.getElementById('loginSubmit');
  if (loginSubmit) loginSubmit.textContent = t('login_submit');
  const loginError = document.getElementById('loginError');
  if (loginError && loginError.dataset && loginError.dataset.errorKey) {
    loginError.textContent = t(loginError.dataset.errorKey);
  }
}

export function initI18n() {
  applyTranslations();
}

export function getSupportedLangs() {
  return ['zh','zh-TW','en','ja','ko'];
}

export function getLangNativeLabel(lang) {
  const map = {
    zh: '简体中文',
    'zh-TW': '繁體中文',
    en: 'English',
    ja: '日本語',
    ko: '한국어'
  };
  return map[lang] || lang;
}