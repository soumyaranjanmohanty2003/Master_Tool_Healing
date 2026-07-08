from playwright.sync_api import Page, expect

# Deliberately brittle: the button's visible text is "Sign In", but this test
# still looks for the old copy "Log In". AutoHeal should diagnose the stale
# selector and fix it to match the current page content.


def test_user_can_sign_in(page: Page):
    page.set_content(
        """
        <html>
          <body>
            <button id="submit-btn">Sign In</button>
          </body>
        </html>
        """
    )

    page.click("text=Log In")
    expect(page.locator("#submit-btn")).to_be_visible()
