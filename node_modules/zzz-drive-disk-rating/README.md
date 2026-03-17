# ZZZ Drive Disk Rating

绝区零驱动盘评分算法库 - Zenless Zone Zero Drive Disk Rating Algorithm Library

一个用于评估绝区零游戏中驱动盘装备评分的TypeScript算法库。

## 功能特性

- 驱动盘评分计算
- 角色全套驱动盘评分
- 多角色批量评分
- 支持自定义角色权重配置
- 品质权重计算（S/A/B）
- 等级权重计算
- 主词条和副词条权重分析
- 评分等级评定
## 下一步的开发计划
- 添加单元测试 ：用于自动化测试和质量保证

## 安装

```bash
npm install zzz-drive-disk-rating
```

## 快速开始

```typescript
import {
  calculateDriveDiscScore,
  calculateCharacterTotalScore,
  calculateAllCharactersScore,
  getCharacterWeights,
  getConfiguredCharacters
} from 'zzz-drive-disk-rating';

// 获取已配置的角色列表
const characters = getConfiguredCharacters();
console.log('已配置的角色:', characters);

// 获取特定角色的权重配置
const weights = getCharacterWeights('叶瞬光');
console.log('角色权重:', weights);

// 计算单个驱动盘评分
const discData = {
  position: 1,
  name: '暴击率驱动盘',
  level: 15,
  rarity: 'S',
  invalidProperty: 0,
  mainProperty: {
    name: '暴击率',
    value: '10.5%'
  },
  subProperties: [
    {
      name: '暴击伤害',
      value: '12.3%',
      level: 3,
      valid: true,
      add: 12.3
    }
  ]
};

const discScore = calculateDriveDiscScore(discData, '叶瞬光');
console.log('驱动盘评分:', discScore);

// 计算角色全套驱动盘评分
const characterData = {
  characterName: '叶瞬光',
  characterFullName: '叶瞬光',
  level: 60,
  profession: 1,
  driveDiscs: [discData]
};

const characterScore = calculateCharacterTotalScore(characterData);
console.log('角色总评分:', characterScore);

// 批量计算多个角色评分
const allCharactersScore = calculateAllCharactersScore([characterData]);
console.log('所有角色评分:', allCharactersScore);
```

## API 文档

### 关于驱动盘

 驱动盘等级上限为15级（A为12级，B为9级），每提升3级将会在当前副词条中随机将一个副词条的等级+1(如果副词条数小于最大词条数那么将出现一条新的副词条)。
 S级驱动盘初始3~4副词条，A级初始2~3，B级初始1~2。
 S级驱动盘最大4副词条，A级最大3副词条，B级最大2副词条。

 

### 配置常量

#### `QUALITY_WEIGHTS`
品质权重配置
```typescript
{
  'S': 1,
  'A': 0.67,
  'B': 0.33
}
```

#### `SLOT_MAIN_POOLS`
每个部位的主词条可选池
```typescript
{
  1: ['生命值'],
  2: ['攻击力'],
  3: ['防御力'],
  4: ['攻击力', '生命值', '防御力', '暴击率', '暴击伤害', '异常精通'],
  5: ['攻击力', '生命值', '防御力', '穿透率', '属性伤害'],
  6: ['攻击力', '生命值', '防御力', '异常掌控', '冲击力', '能量自动回复']
}
```

#### `SUB_STATS_POOL`
副词条可选池
```typescript
[
  '生命值', '攻击力', '防御力',
  '暴击率', '暴击伤害', '异常精通',
  '穿透值', '小生命', '小攻击', '小防御'
]
```

#### `characterWeights`
角色权重配置对象

### 主要函数

#### `calculateDriveDiscScore(disc, characterName)`
计算单个驱动盘的评分

**参数：**
- `disc: DriveDisc` - 驱动盘数据
- `characterName: string` - 角色名称

**返回：** `DriveDiscScoreResult`

#### `calculateCharacterTotalScore(characterData)`
计算角色全套驱动盘的总评分

**参数：**
- `characterData: CharacterData` - 角色数据

**返回：** `CharacterScoreResult`

#### `calculateAllCharactersScore(charactersData)`
批量计算多个角色的评分

**参数：**
- `charactersData: CharacterData[]` - 角色数据数组

**返回：** `AllCharactersScoreResult[]`

#### `getCharacterWeights(characterName)`
获取指定角色的权重配置

**参数：**
- `characterName: string` - 角色名称

**返回：** 权重配置对象

#### `getConfiguredCharacters()`
获取所有已配置的角色名称列表

**返回：** `string[]`

#### `calculateGrade(finalScore)`
根据评分计算等级

**参数：**
- `finalScore: number` - 最终评分

**返回：** `GradeResult`

### 类型定义

#### `DriveDisc`
驱动盘数据结构
```typescript
interface DriveDisc {
  position: number;           // 部位 (1-6)
  name: string;              // 驱动盘名称
  level: number;             // 等级
  rarity: 'S' | 'A' | 'B';   // 品质
  invalidProperty: number;    // 无效词条数量
  mainProperty: MainProperty; // 主词条
  subProperties: SubProperty[]; // 副词条数组
}
```

#### `CharacterData`
角色数据结构
```typescript
interface CharacterData {
  characterName: string;      // 角色名称
  characterFullName: string;  // 角色全名
  level: number;             // 角色等级
  profession: number;         // 职业
  driveDiscs: DriveDisc[];    // 驱动盘数组
}
```

#### `DriveDiscScoreResult`
驱动盘评分结果
```typescript
interface DriveDiscScoreResult {
  score: number;                    // 评分
  subPropertiesWeight: number;      // 副词条权重
  mainPropertyWeight: number;       // 主词条权重
  maxWeightInfo: MaxWeightInfo;     // 最大权重信息
  validProperties: ValidPropertyDetail[]; // 有效词条详情
  qualityWeight: number;            // 品质权重
  levelWeight: number;              // 等级权重
  gradeResult?: GradeResult;        // 等级结果
}
```

#### `CharacterScoreResult`
角色评分结果
```typescript
interface CharacterScoreResult {
  totalScore: number;               // 总评分
  discScores: { [position: number]: number }; // 各部位评分
  discDetails: Array<{              // 驱动盘详情
    position: number;
    name: string;
    level: number;
    rarity: string;
    mainProperty: MainProperty;
    score: number;
    details: DriveDiscScoreResult;
  }>;
}
```

## 开发

### 构建

```bash
npm run build
```

### 发布到npm

```bash
npm publish
```

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License

## 链接

- [GitHub 仓库](https://github.com/chenshuo318-dotcom/zzz_drive-disk-rating)
- [npm 包](https://www.npmjs.com/package/zzz-drive-disk-rating)

## 致谢

感谢所有使用和贡献本项目的开发者！
