# 麦当劳 MCP 领券客户端

一个直连麦当劳中国官方 MCP Server 的脚本：查询当前可领的优惠券，并一键全部领取。

## 功能

| 步骤 | 工具 | 说明 |
|---|---|---|
| 初始化 | `initialize` | 与 MCP Server 握手（协议版本 2025-06-18） |
| 查券 | `available-coupons` | 查询麦麦省当前可领取的优惠券列表 |
| 领券 | `auto-bind-coupons` | 一键领取全部可领优惠券 |
| 验证 | `query-my-coupons` | 查看卡包内已有的优惠券 |

## 使用方法

1. 申请 MCP Token：打开 https://open.mcd.cn/mcp ，手机号登录后在「控制台」激活申请
2. 提供 Token（二选一）：
   - 设置环境变量：`export MCD_MCP_TOKEN="你的Token"`
   - 或在 MCP 客户端配置 `~/.workbuddy/mcp.json` 的 `mcd-mcp` 条目中填写（脚本会自动读取）
3. 运行：

```bash
python mcd_mcp_client.py
```

## 官方 MCP 配置参考

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamableHttp",
      "url": "https://mcp.mcd.cn/mcp-servers/mcd-mcp",
      "headers": { "Authorization": "Bearer YOUR_MCP_TOKEN" }
    }
  }
}
```

## 安全与限制

- 脚本不硬编码 Token，请勿把 Token 提交到仓库；如疑似泄露，到控制台删除重置
- MCP Server 仅支持 MCP Version 2025-06-18 及更早版本
- 每 Token 限流 600 次/分钟
- 服务由麦当劳中国官方提供，面向中国大陆地区（不含港澳台）

## 依赖

仅 Python 标准库，无第三方依赖。
