const express = require('express');
const { v4: uuidv4 } = require('uuid');
const {
  calculateDriveDiscScore,
  calculateCharacterTotalScore,
  getCharacterWeights,
  getConfiguredCharacters
} = require('zzz-drive-disk-rating');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());// 解析 JSON 格式的请求体

// 健康检查接口
app.get('/health', (req, res) => {
  res.json({ success: true, message: 'Node.js service is running' });
});

// 暴露 API 接口，供 Python 调用
app.post('/node-function', (req, res) => {
  try {
    // 1. 接收 Python 传来的驱动盘数据
    const { diskData, characterName } = req.body;
    
    if (!diskData) {
      return res.status(400).json({ success: false, error: 'Missing diskData parameter' });
    }
    
    // 2. 初始化结果对象
    const result = {
      uniqueId: uuidv4(),
      timestamp: Date.now()
    };
    
    // 3. 根据数据类型选择合适的评分函数
    try {
      if (Array.isArray(diskData) && diskData.length > 0 && diskData[0].position !== undefined) {
        // 多个驱动盘 - 角色全套驱动盘评分
        if (!characterName) {
          throw new Error('characterName is required for multiple drive discs');
        }
        const characterScore = calculateCharacterTotalScore(diskData, characterName);
        result.characterScore = characterScore;
      } else if (diskData.position !== undefined) {
        // 单个驱动盘评分
        const discScore = calculateDriveDiscScore(diskData, characterName || '通用');
        result.diskScore = discScore;
      } else {
        throw new Error('Invalid diskData format. Expected DriveDisc object or array of DriveDisc objects');
      }
    } catch (diskError) {
      console.error('Drive disk rating error:', diskError);
      result.diskRatingError = diskError.message;
    }

    // 4. 返回处理结果给 Python
    res.json({ success: true, data: result });
  } catch (error) {
    console.error('Processing error:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

// 获取支持的角色列表
app.get('/characters', (req, res) => {
  try {
    const characters = getConfiguredCharacters();
    res.json({ success: true, data: { characters } });
  } catch (error) {
    console.error('Error getting characters:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

// 获取角色权重配置
app.get('/character-weights/:characterName', (req, res) => {
  try {
    const { characterName } = req.params;
    const weights = getCharacterWeights(characterName);
    res.json({ success: true, data: { characterName, weights } });
  } catch (error) {
    console.error('Error getting character weights:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

// 启动服务
app.listen(PORT, () => {
  console.log(`Node.js service running on port ${PORT}`);
  console.log(`Health check: http://localhost:${PORT}/health`);
  console.log(`API endpoint: http://localhost:${PORT}/node-function`);
  console.log(`Characters endpoint: http://localhost:${PORT}/characters`);
  console.log(`Character weights endpoint: http://localhost:${PORT}/character-weights/{characterName}`);
});