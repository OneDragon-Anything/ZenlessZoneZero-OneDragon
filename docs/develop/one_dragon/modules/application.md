# Application

应用，在一条龙框架中，通常是一系列 Operation 的组合，用于完成一个具体的任务。

`Application`继承于[Operation](operation.md)，拥有`Operation`的相同的编排能力，并添加应用配置和运行记录等功能。

## 应用工厂

每个自定义应用，需要继承实现 `ApplicationFactory` 类，用于定义应用唯一标识和提供应用相关内容的创建方式。

## 自定义应用

需继承 `Application` 类，进行任务的操作编排。

(待补充更多说明)

## 应用配置

需继承 `ApplicationConfig` 类，用于定义应用所需配置。

应用配置的维度是 `app_id` + `instance_idx` + `group_id`，即应用(app_id)在不同的账号(instance_idx)和不同的应用组(group_id)中，可以有不同的配置。

(待补充更多说明)

## 运行记录

需继承 `ApplicationRunRecord` 类，用于定义应用的运行记录。

一个任务的运行记录应该是账号下唯一的，即不管分配到哪些应用组中，要完成的内容是固定的。

所以运行记录的维度是 `app_id` + `instance_idx`，即应用(app_id)在不同的账号(instance_idx)中，有不同的运行记录。

(待补充更多说明)


## 应用组

(待补充)


## 应用服务 - ApplicationService

