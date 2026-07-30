# AWS 重点资源事件飞书加急通知方案

基于 Amazon EventBridge + Lambda 的事件通知方案，将 AWS 账户内的各类事件（Health、EC2、RDS 等）实时推送到飞书群聊，并支持对重点资源按需配置电话、短信、应用内加急等方式通知相关人员，确保关键告警不被遗漏。

## 需求背景

- AWS 账户内发生的 Health 事件（如实例自动恢复、计划维护）需要及时通知运维人员
- 关键实例的状态变化（停止、终止、状态检查失败）需要第一时间告警
- 不同紧急程度的事件需要不同的通知方式（群消息 / 电话加急 / 短信加急）
- 需要支持灵活扩展，覆盖更多 AWS 服务的事件类型

## 使用场景

| 场景 | 事件来源 | 示例 |
|---|---|---|
| EC2 实例异常恢复 | AWS Health | Auto Recovery Success / Failure |
| EC2 计划维护 | AWS Health | Reboot / Stop Scheduled |
| EC2 实例状态变化 | EC2 | State-change: stopped, terminated |
| EC2 状态检查失败 | EC2 | System / Instance Status Check Failed |
| RDS 故障转移 | RDS | Failover, Maintenance Scheduled |
| 其他 AWS 服务事件 | 各服务 | 按需配置 EventBridge 规则 |

## 架构

```
  ┌──────────────┐
  │  AWS Health  │──┐
  │  (所有服务)   │  │
  └──────────────┘  │     ┌──────────────────────────────────────┐
                    │     │        Amazon EventBridge             │
  ┌──────────────┐  │     │                                      │
  │   EC2        │──┤     │  ┌──────────────┐                    │
  │ State-change │  ├────▶│  │ HealthPush   │──────────────────┐ │
  │ Status Check │  │     │  │ (Health事件)  │                  │ │
  └──────────────┘  │     │  └──────────────┘                  │ │
                    │     │                                    │ │
  ┌──────────────┐  │     │  ┌──────────────────┐             │ │
  │  RDS / 其他  │──┘     │  │ EC2Status        │─────────────┤ │
  │  服务事件     │        │  │ Monitor          │             │ │
  └──────────────┘        │  │ (EC2指定实例监控) │             │ │
                          │  └──────────────────┘             │ │
                          │                                    │ │
                          │  ┌──────────────────┐             │ │
                          │  │ 更多自定义规则... │─────────────┤ │
                          │  │ (RDS/ECS/...)    │             │ │
                          │  └──────────────────┘             │ │
                          └───────────────────────────────────┼─┘
                                                              │
                                                              ▼
                                    ┌─────────────────────────────────┐
                                    │     lark-urgent-sender Lambda   │
                                    │                                 │
                                    │  环境变量控制加急方式:            │
                                    │  ├─ ENABLE_PHONE_URGENT (电话)  │
                                    │  ├─ ENABLE_SMS_URGENT   (短信)  │
                                    │  └─ ENABLE_APP_URGENT   (应用)  │
                                    │                                 │
                                    │  飞书配置:                       │
                                    │  ├─ APP_ID / APP_SECRET         │
                                    │  ├─ CHAT_ID (群聊)              │
                                    │  └─ RECEIVE_USER_ID (接收人)    │
                                    └────────────┬────────────────────┘
                                                 │
                                                 ▼
                                         ┌──────────────┐
                                         │   飞书 Lark   │
                                         │  ├─ 群消息    │
                                         │  ├─ 电话加急  │
                                         │  ├─ 短信加急  │
                                         │  └─ 应用加急  │
                                         └──────────────┘
```

## 核心组件

| 组件 | 说明 |
|---|---|
| **HealthPush** | EventBridge 规则，捕获指定资源的 Health 事件，触发 Lambda |
| **EC2StatusMonitor** | EventBridge 规则，捕获指定 EC2 实例的状态变化和检查失败 |
| **lark-urgent-sender** | Lambda 函数，发送飞书群消息并通过环境变量控制加急方式 |

## 加急方式配置

通过 Lambda 环境变量灵活控制通知方式，无需修改代码：

| 环境变量 | 说明 | 值 |
|---|---|---|
| `ENABLE_PHONE_URGENT` | 电话加急 | `true` / `false` |
| `ENABLE_SMS_URGENT` | 短信加急 | `true` / `false` |
| `ENABLE_APP_URGENT` | 应用内加急 | `true` / `false` |
| `CHAT_ID` | 飞书群聊 ID | 群聊 ID |
| `RECEIVE_USER_ID` | 加急接收人 | 飞书用户 ID |
| `APP_ID` / `APP_SECRET` | 飞书应用凭证 | 应用凭证 |
| `LOG_LEVEL` | 业务日志级别 | `INFO` |
| `LARK_LOG_LEVEL` | Lark SDK 日志级别 | `INFO` |

各加急方式的通知内容：

| 加急方式 | 通知内容 |
|---|---|
| 群消息 | Lambda 收到的事件内容（可通过 EventBridge 规则的 Input Transformer 自定义格式） |
| 应用内加急 | 飞书 App 内弹窗提醒，点击可查看消息详情 |
| 短信加急 | 【飞书】有人给你发了一条加急消息，请打开飞书查看详情。 |
| 电话加急 | "<机器人名称>给你发了一条加急消息，请打开飞书查看详情。" |

> 短信和电话加急的通知内容由飞书平台固定生成，不可自定义。其中电话加急中的"机器人名称"为创建飞书应用时设置的机器人名称。具体事件详情需打开飞书查看群消息。

修改示例：
```bash
aws lambda update-function-configuration \
  --function-name lark-urgent-sender \
  --environment 'Variables={ENABLE_PHONE_URGENT=true,ENABLE_SMS_URGENT=false,ENABLE_APP_URGENT=true,APP_ID=<app_id>,APP_SECRET=<app_secret>,CHAT_ID=<chat_id>,RECEIVE_USER_ID=<user_id>,LOG_LEVEL=INFO,LARK_LOG_LEVEL=INFO}' \
  --region cn-northwest-1
```

## 部署步骤

### 1. 创建飞书应用

前往 [飞书开放平台](https://open.feishu.cn/app) 创建企业自建应用，启用机器人能力，并添加以下权限：

| 权限 | 权限标识 | 说明 |
|---|---|---|
| 获取用户 user ID | `contact:user.employee_id:readonly` | 获取加急目标用户 |
| 获取与发送单聊、群组消息 | `im:message` | 发送消息基础权限 |
| 以应用的身份发消息 | `im:message:send_as_bot` | 机器人身份发送消息 |
| 发送应用内加急消息 | `im:message.urgent` | 应用内加急 |
| 发送短信加急消息 | `im:message.urgent:sms` | 短信加急（按需开启） |
| 发送电话加急消息 | `im:message.urgent:phone` | 电话加急（按需开启） |

配置完成后，记录以下信息：

- **App ID** 和 **App Secret**：在应用的「凭证与基础信息」页面获取
- **Chat ID（群聊 ID）**：将机器人添加到目标群聊后，通过飞书 API [获取群信息](https://open.feishu.cn/document/server-docs/group/chat/get) 或在群设置中查看
- **Receive User ID（加急接收人用户 ID）**：在飞书管理后台 > 通讯录中查看用户的 `user_id`，或通过 [获取用户信息 API](https://open.feishu.cn/document/server-docs/contact-v3/user/get) 获取

> 如启用了电话加急，建议将飞书加急电话号码添加至手机通讯录，防止来电被拦截。详见：[将飞书加急电话添加至设备通讯录](https://www.feishu.cn/hc/zh-CN/articles/196508164398)

### 2. 创建 IAM 执行角色

在 [IAM 控制台](https://console.amazonaws.cn/iam/home#/roles) 创建角色，或通过 CLI：

```bash
cat > trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "lambda.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

aws iam create-role \
  --role-name lark-urgent-lambda-role \
  --assume-role-policy-document file://trust-policy.json

aws iam attach-role-policy \
  --role-name lark-urgent-lambda-role \
  --policy-arn arn:aws-cn:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
```

> 角色创建后等待约 10 秒再创建 Lambda，否则可能报 `InvalidParameterValueException`。

### 3. 部署 Lambda 函数

将 `lambda_function.py` 与 `lark_oapi` 依赖打包为 zip，在 [Lambda 控制台](https://console.amazonaws.cn/lambda/home?region=cn-northwest-1#/functions) 创建函数，或通过 CLI：

```bash
ROLE_ARN=$(aws iam get-role --role-name lark-urgent-lambda-role --query 'Role.Arn' --output text)

aws lambda create-function \
  --function-name lark-urgent-sender \
  --runtime python3.12 \
  --handler lambda_function.lambda_handler \
  --role "$ROLE_ARN" \
  --zip-file fileb://lark_urgent_lambda.zip \
  --timeout 300 \
  --memory-size 256 \
  --environment 'Variables={APP_ID=<app_id>,APP_SECRET=<app_secret>,RECEIVE_USER_ID=<user_id>,CHAT_ID=<chat_id>,ENABLE_APP_URGENT=true,ENABLE_SMS_URGENT=false,ENABLE_PHONE_URGENT=false,LOG_LEVEL=INFO,LARK_LOG_LEVEL=INFO}' \
  --region cn-northwest-1
```

> 内存设为 256MB 是因为 lark_oapi 包较大，128MB 下冷启动会超时。

### 4. 创建 EventBridge 规则

在 [EventBridge 控制台](https://console.amazonaws.cn/events/home?region=cn-northwest-1#/rules) 创建规则，或通过 CLI。以下以 EC2 实例监控为例：

#### 4.1 Health 事件规则（监听指定实例的 Health 事件）

```bash
aws events put-rule \
  --name HealthPush \
  --event-pattern '{
    "source": ["aws.health", "self.test.aws.health"],
    "detail-type": ["AWS Health Event"],
    "resources": ["i-052aea9e0f22d4742", "i-0f59a6e7b3887fb8f"]
  }' \
  --state ENABLED \
  --region cn-northwest-1
```

#### 4.2 EC2 实例状态监控规则（监听指定实例的状态变化和检查失败）

```bash
aws events put-rule \
  --name EC2StatusMonitor \
  --event-pattern '{
    "source": ["aws.ec2", "self.test.aws.ec2"],
    "detail-type": [
      "EC2 Instance State-change Notification",
      "EC2 Instance Status Check Failed (System)",
      "EC2 Instance Status Check Failed (Instance)",
      "EC2 Instance Status Check Failed"
    ],
    "detail": {
      "instance-id": ["i-052aea9e0f22d4742", "i-0f59a6e7b3887fb8f"]
    }
  }' \
  --description "EC2 status change and check failed for specific instances" \
  --state ENABLED \
  --region cn-northwest-1
```

#### 4.3 为规则添加 Lambda 目标

```bash
LAMBDA_ARN="arn:aws-cn:lambda:cn-northwest-1:<ACCOUNT_ID>:function:lark-urgent-sender"

# HealthPush 目标
aws events put-targets --rule HealthPush \
  --targets "[{\"Id\":\"LarkUrgentTarget\",\"Arn\":\"$LAMBDA_ARN\"}]" \
  --region cn-northwest-1

# EC2StatusMonitor 目标
aws events put-targets --rule EC2StatusMonitor \
  --targets "[{\"Id\":\"LarkUrgentTarget\",\"Arn\":\"$LAMBDA_ARN\"}]" \
  --region cn-northwest-1
```

#### 4.4 授权 EventBridge 调用 Lambda

```bash
aws lambda add-permission \
  --function-name lark-urgent-sender \
  --statement-id AllowEventBridgeHealthPush \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws-cn:events:cn-northwest-1:<ACCOUNT_ID>:rule/HealthPush \
  --region cn-northwest-1

aws lambda add-permission \
  --function-name lark-urgent-sender \
  --statement-id AllowEventBridgeEC2StatusMonitor \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws-cn:events:cn-northwest-1:<ACCOUNT_ID>:rule/EC2StatusMonitor \
  --region cn-northwest-1
```

### 5. 添加更多监控实例

更新规则的 event pattern 中的实例 ID 列表即可：

```bash
aws events put-rule --name EC2StatusMonitor \
  --event-pattern '{
    "source": ["aws.ec2", "self.test.aws.ec2"],
    "detail-type": ["EC2 Instance State-change Notification", "EC2 Instance Status Check Failed (System)", "EC2 Instance Status Check Failed (Instance)", "EC2 Instance Status Check Failed"],
    "detail": {
      "instance-id": ["i-052aea9e0f22d4742", "i-0f59a6e7b3887fb8f", "<新增实例ID>"]
    }
  }' \
  --state ENABLED --region cn-northwest-1
```

## 测试

### 测试 Health 事件（模拟 Auto Recovery 成功）

```bash
aws events put-events --entries '[{
  "Source": "self.test.aws.health",
  "DetailType": "AWS Health Event",
  "Detail": "{\"eventArn\":\"arn:aws-cn:health:cn-northwest-1::event/EC2/AWS_EC2_SIMPLIFIED_AUTO_RECOVERY_SUCCESS/TEST\",\"service\":\"EC2\",\"eventTypeCode\":\"AWS_EC2_SIMPLIFIED_AUTO_RECOVERY_SUCCESS\",\"eventTypeCategory\":\"issue\",\"startTime\":\"2026-04-09T11:55:00Z\",\"eventDescription\":[{\"latestDescription\":\"Your EC2 instance i-052aea9e0f22d4742 was successfully recovered.\"}],\"affectedEntities\":[{\"entityValue\":\"i-052aea9e0f22d4742\"}]}",
  "Resources": ["i-052aea9e0f22d4742"],
  "EventBusName": "default"
}]' --region cn-northwest-1
```

### 测试 EC2 状态变化（模拟异常重启全过程）

Auto Recovery 场景下实例会经历 `stopped → pending → running` 三次状态变化：

```bash
# 1. 实例被停止
aws events put-events --entries '[{
  "Source": "self.test.aws.ec2",
  "DetailType": "EC2 Instance State-change Notification",
  "Detail": "{\"instance-id\":\"i-052aea9e0f22d4742\",\"state\":\"stopped\"}",
  "Resources": ["arn:aws-cn:ec2:cn-northwest-1:<ACCOUNT_ID>:instance/i-052aea9e0f22d4742"],
  "EventBusName": "default"
}]' --region cn-northwest-1

# 2. 实例恢复中
aws events put-events --entries '[{
  "Source": "self.test.aws.ec2",
  "DetailType": "EC2 Instance State-change Notification",
  "Detail": "{\"instance-id\":\"i-052aea9e0f22d4742\",\"state\":\"pending\"}",
  "Resources": ["arn:aws-cn:ec2:cn-northwest-1:<ACCOUNT_ID>:instance/i-052aea9e0f22d4742"],
  "EventBusName": "default"
}]' --region cn-northwest-1

# 3. 实例恢复完成
aws events put-events --entries '[{
  "Source": "self.test.aws.ec2",
  "DetailType": "EC2 Instance State-change Notification",
  "Detail": "{\"instance-id\":\"i-052aea9e0f22d4742\",\"state\":\"running\"}",
  "Resources": ["arn:aws-cn:ec2:cn-northwest-1:<ACCOUNT_ID>:instance/i-052aea9e0f22d4742"],
  "EventBusName": "default"
}]' --region cn-northwest-1
```

### 验证

检查 Lambda 执行日志：

```bash
aws logs tail /aws/lambda/lark-urgent-sender --since 10m --region cn-northwest-1
```

> **注意**: 测试时使用 `self.test.aws.health` 和 `self.test.aws.ec2` 作为 source，因为 `aws.health` 和 `aws.ec2` 是 AWS 保留的 source，不允许用户直接发送。生产环境中真实事件会自动使用 `aws.*` source 触发规则。

## 扩展

本方案不限于 EC2 事件，可通过新增 EventBridge 规则扩展到任意 AWS 服务：

```bash
# 示例: 监控 RDS Health 事件
aws events put-rule --name RDSHealthMonitor \
  --event-pattern '{"source":["aws.health"],"detail":{"service":["RDS"]}}' \
  --state ENABLED --region cn-northwest-1

# 示例: 监控所有服务的 Health 事件（去掉 resources 过滤）
aws events put-rule --name AllHealthEvents \
  --event-pattern '{"source":["aws.health"],"detail-type":["AWS Health Event"]}' \
  --state ENABLED --region cn-northwest-1
```

添加规则后，将 target 指向 `lark-urgent-sender` Lambda 并授权即可。
