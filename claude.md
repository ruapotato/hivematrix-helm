# Claude Code Instructions

## Commit Guidelines

### When to Commit
- Only commit when a feature is **completed and working**
- Only commit when the user asks, or when a feature is truly done
- Do NOT commit after every small change or prompt

### Good Commit Examples
- "Add view switcher with three modes (Icons, Compact, Tree)" - one commit for entire feature
- "Improve edit page UX and dark mode support" - groups related improvements together
- "Fix button sizing and alignment issues" - bundles all related button fixes

### Bad Commit Examples (Don't do this!)
- Committing every tiny CSS tweak separately
- Multiple commits trying different approaches to fix the same bug
- Separate commits for "fix icons", "fix icons again", "nuclear fix for icons"

### Testing Before Committing
- Test the feature works as expected
- Verify no regressions were introduced
- Make sure the commit is complete and logical

### Commit Message Format
- Use clear, descriptive commit messages
- Start with a verb (Add, Fix, Update, Remove, Improve, etc.)
- Be concise but informative
- Group related changes into a single logical commit
