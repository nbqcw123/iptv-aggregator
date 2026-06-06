# IPTV 聚合器 - 快捷命令

.PHONY: help build run test clean

help: ## 显示帮助
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

build: ## 构建前端 + Docker 镜像
	cd frontend && npm install && npm run build
	docker build -t iptv-aggregator .

run: ## 启动服务
	docker-compose up -d
	@echo "✅ 服务已启动: http://localhost:8080"

stop: ## 停止服务
	docker-compose down

restart: ## 重启服务
	docker-compose restart

logs: ## 查看日志
	docker-compose logs -f

test: ## 运行后端测试
	cd backend && source .venv/bin/activate && python3 -c "from app.main import app; print('✅ OK')"

update-readme: ## 更新 README 版本号
	bash scripts/update_readme.sh

clean: ## 清理构建产物
	rm -rf frontend/node_modules frontend/dist backend/app/static backend/.venv
	find . -type d -name __pycache__ -exec rm -rf {} +
