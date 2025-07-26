import os
import random
import time
import pytest
from playwright.sync_api import Playwright, Page
from pathlib import Path

# 获取符合大小限制的随机测试文件 (小于1MB)
def get_random_test_file() -> str:
    system_dirs = [
        r'C:\Windows\Fonts',
        r'C:\Windows\System32\DriverStore\FileRepository',
        r'C:\Windows\System32\wbem'
    ]

    candidate_files = []
    for dir_path in system_dirs:
        if not os.path.exists(dir_path):
            continue
        for root, _, files in os.walk(dir_path):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    file_size = os.path.getsize(file_path)
                    # 选择10KB到1MB之间的文件
                    if 10240 < file_size < 1048576:
                        candidate_files.append(file_path)
                except (OSError, PermissionError):
                    continue

    if not candidate_files:
        raise Exception("未找到符合条件的测试文件")
    return random.choice(candidate_files)

@pytest.fixture(scope="session")
def test_file():
    return get_random_test_file()

@pytest.fixture(scope="function")
def page(playwright: Playwright):
    browser = playwright.chromium.launch(
        headless=False,  # 开发阶段设为False方便观察
        args=["--start-maximized"]
    )
    context = browser.new_context(no_viewport=True)
    page = context.new_page()
    page.set_default_timeout(3000)
    page.set_default_navigation_timeout(3000)
    yield page
    context.close()
    browser.close()

def test_create_group_and_upload_file(page: Page, test_file: str):
    # 导航到首页
    page.goto("http://localhost:5000")
    page.wait_for_load_state("networkidle")

    # 点击创建小组按钮
    page.click("text=创建新小组")
    page.wait_for_url("**/create")

    # 填写小组信息
    group_name = f"测试小组_{int(time.time())}"
    page.fill("input[name='group_name']", group_name)
    page.select_option("select[name='duration']", "24")
    page.fill("input[name='password']", "test123")
    page.check("#allowConvertToReadonly")

    with page.expect_navigation():
        page.click("text=创建小组")

    # 验证小组创建成功
    assert group_name in page.text_content("h1")

    # 上传文件
    # 第一步：点击"选择文件"按钮触发文件选择对话框
    with page.expect_file_chooser() as fc_info:
        page.click("text=选择文件")
    file_chooser = fc_info.value
    file_chooser.set_files(test_file)
    
    # 第二步：等待文件选择完成后点击"上传"按钮
    page.click("button:has-text('上传文件')")

    # 验证文件上传成功
    page.wait_for_selector(f"text={os.path.basename(test_file)}")
    assert page.is_visible(f"text={os.path.basename(test_file)}")


def test_convert_to_readonly(page: Page):
    # 创建小组
    page.goto("http://localhost:5000/group/create")
    group_name = f"测试只读小组_{int(time.time())}"

    page.fill("input[name='group_name']", group_name)
    page.select_option("select[name='duration']", "24")
    
    page.select_option("select[name='duration']", "24")

    page.check("#allowConvertToReadonly")

    with page.expect_navigation():
        page.click("button:has-text('创建小组')")
    
    # 验证小组创建成功
    assert group_name in page.text_content("h1")

    def handle_confirm_dialog(dialog):
        dialog.accept()
    page.on("dialog", handle_confirm_dialog)

    # 点击转换为只读按钮并处理确认对话框
    page.click("#convertToReadonlyBtn")
    page.wait_for_timeout(1000)
    page.remove_listener('dialog', handle_confirm_dialog)

    # 等待页面刷新并验证只读状态
    page.wait_for_load_state("domcontentloaded")
    assert page.is_visible("text=只读")

    # 验证上传按钮已禁用
    upload_button = page.locator("button:has-text('上传文件')")
    assert upload_button.count() == 0