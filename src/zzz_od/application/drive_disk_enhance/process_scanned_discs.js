const fs = require('fs');
const path = require('path');

// 导入评分模块
const { 
  calculateDriveDiscScore, 
  getCharacterWeights,
  getConfiguredCharacters,
  optimizeDriveDisc 
} = require('zzz-drive-disk-rating');

// 读取命令行参数
const inputFile = process.argv[2];
const characterName = process.argv[3] || '露西亚'; // 默认角色

// 检查是否请求角色列表
if (inputFile === '--list-characters') {
  const characters = getConfiguredCharacters();
  console.log(JSON.stringify(characters));
  process.exit(0);
}

// 输出调试信息
console.error(`[DEBUG] 输入文件: ${inputFile}`);
console.error(`[DEBUG] 角色名称: ${characterName}`);

if (!inputFile) {
  console.error('错误: 请提供输入文件路径');
  console.error('用法: node process_scanned_discs.js <输入文件> [角色名称]');
  console.error('示例: node process_scanned_discs.js scanned_discs.json 露西亚');
  console.error('获取角色列表: node process_scanned_discs.js --list-characters');
  process.exit(1);
}

try {
  // 检查文件是否存在
  if (!fs.existsSync(inputFile)) {
    console.error(`错误: 输入文件不存在: ${inputFile}`);
    process.exit(1);
  }
  
  // 读取扫描的驱动盘数据
  const fileContent = fs.readFileSync(inputFile, 'utf-8');
  console.error(`[DEBUG] 文件大小: ${fileContent.length} 字符`);
  
  const scannedDiscs = JSON.parse(fileContent);
  console.error(`[DEBUG] 驱动盘数量: ${scannedDiscs.length}`);
  
  console.error(`[DEBUG] 正在处理 ${scannedDiscs.length} 个驱动盘...`);
  console.error(`[DEBUG] 角色: ${characterName}`);
  
  // 获取角色权重配置
  const weightConfig = getCharacterWeights(characterName);
  
  if (!weightConfig) {
    console.error(`错误: 未找到角色 "${characterName}" 的权重配置`);
    console.error('可用角色:', getConfiguredCharacters());
    process.exit(1);
  }
  
  console.error(`[DEBUG] 角色权重配置已加载`);
  
  // 计算每个驱动盘的评分
  const results = scannedDiscs.map((disc, index) => {
    try {
      // 优化驱动盘（计算潜力值）
      const optimizedDisc = optimizeDriveDisc(disc, characterName);
      
      // 计算优化后的评分（潜力值）
      const scoreResult = calculateDriveDiscScore(optimizedDisc, characterName);
      
      // 计算原始评分
      const originalScoreResult = calculateDriveDiscScore(disc, characterName);
      
      return {
        index,
        disc: disc,
        optimizedDisc: optimizedDisc,
        currentScore: originalScoreResult.score,
        currentDetails: originalScoreResult,
        potentialScore: scoreResult.score,
        potentialDetails: scoreResult,
        grade: scoreResult.gradeResult?.grade || '未知',
        gradeClass: scoreResult.gradeResult?.gradeClass || '',
        gradeDesc: scoreResult.gradeResult?.gradeDesc || ''
      };
    } catch (error) {
      console.error(`[ERROR] 驱动盘 ${index} 处理失败: ${error.message}`);
      return {
        index,
        disc: disc,
        error: error.message
      };
    }
  });
  
  console.error(`[DEBUG] 计算完成，结果数量: ${results.length}`);
  
  // 输出结果（JSON格式）到 stdout
  const output = JSON.stringify(results, null, 2);
  console.log(output);
  
} catch (error) {
  console.error(`[FATAL ERROR] 处理失败: ${error.message}`);
  console.error(error.stack);
  process.exit(1);
}
