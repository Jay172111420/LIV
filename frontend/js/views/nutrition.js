import { api } from '../api.js';
import { h } from '../dom.js';
import { labelFor } from '../units.js';
import { Empty, SectionHeader, loadInto } from '../ui/components.js';

export function renderNutrition(root) {
  const content = h('div', { class: 'stack' });
  root.replaceChildren(h('div', {}, SectionHeader('Nutrition', 'Your calorie and macro targets.'), content));

  loadInto(content, () => api.nutritionProfile(), (n) => {
    const hasTargets = [n.calorie_target, n.protein_g, n.carbs_g, n.fat_g].some((v) => v != null);
    const tags = (items) => (items.length ? items.map((t) => h('span', { class: 'badge' }, t)) : 'None');

    return [
      h('section', { class: 'card' },
        h('h2', { class: 'section-title-sm' }, 'Daily targets'),
        hasTargets
          ? h('dl', { class: 'defs' },
              h('dt', {}, 'Calories'), h('dd', {}, n.calorie_target != null ? `${n.calorie_target} kcal` : 'Not set'),
              h('dt', {}, 'Protein'), h('dd', {}, n.protein_g != null ? `${n.protein_g} g` : 'Not set'),
              h('dt', {}, 'Carbohydrate'), h('dd', {}, n.carbs_g != null ? `${n.carbs_g} g` : 'Not set'),
              h('dt', {}, 'Fat'), h('dd', {}, n.fat_g != null ? `${n.fat_g} g` : 'Not set'))
          : Empty({ title: 'No targets set', text: 'Food logging and automatic calorie and macro targets arrive in a later update.' })),
      h('section', { class: 'card' },
        h('h2', { class: 'section-title-sm' }, 'Dietary needs'),
        h('dl', { class: 'defs' },
          h('dt', {}, 'Preference'), h('dd', {}, labelFor(n.dietary_preference)),
          h('dt', {}, 'Allergies'), h('dd', { class: 'chips' }, tags(n.allergies)),
          h('dt', {}, 'Restrictions'), h('dd', { class: 'chips' }, tags(n.restrictions)))),
    ];
  });
}
