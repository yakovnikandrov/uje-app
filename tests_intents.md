# tests_intents.md — Тестовые фразы бота «Уже»

Отмечай ✅ / ❌. Цель: 90% попаданий в action.

## Память — сохранить (10)
| Фраза | Ожидаемый action |
|---|---|
| Меня зовут Яков | save_fact / name |
| Я живу в Москве | save_fact / city |
| Я работаю дизайнером | save_fact / job |
| Я люблю капучино | save_fact / coffee |
| У меня кот Барсик | save_fact / pets |
| Я живу на Ленина 10 | save_fact / home_address |
| Офис на Тверской 5 | save_fact / work_address |
| У меня аллергия на лактозу | save_fact / allergy |
| Люблю кофейню на углу | save_fact / favorite_place |
| Запомни: зови меня Босс | save_fact / name |

## Память — просмотр и удаление (5)
| Фраза | Ожидаемый action |
|---|---|
| Покажи память | get_memory |
| Что ты помнишь? | get_memory |
| Забудь про кофе | delete_fact / coffee |
| Удали адрес | delete_fact / home_address |
| Забудь всё | get_memory (или delete_fact, если добавим) |

## Действия (10)
| Фраза | Ожидаемый action |
|---|---|
| Уже, домой | route_home |
| Отвези домой | route_home |
| Какой мой кофе? | my_coffee |
| Мой кофе | my_coffee |
| Что ты обо мне знаешь? | about_me |
| О себе | about_me |
| Моя мощь | manifesto |
| Чем ты лучше ChatGPT? | manifesto |
| Что по афише? | show_afisha |
| Покажи афишу | show_afisha |

## Болталка (10)
| Фраза | Ожидаемый action |
|---|---|
| Привет | chat |
| Как дела? | chat |
| Спасибо | chat |
| Ты кто? | chat |
| Доброе утро | chat |
| Что умеешь? | chat |
| Расскажи шутку | chat |
| Который час? | chat |
| Ты живой? | chat |
| Спокойной ночи | chat |

## Непонятное (5)
| Фраза | Ожидаемый action |
|---|---|
| Сделай бутерброд | unknown |
| Вызови вертолёт | unknown |
| Забронируй билет на Марс | unknown |
| Асдфгх | unknown |
| Купи мне слона | unknown |

## Пустая память и ошибки (5)
| Фраза | Ожидаемый ответ |
|---|---|
| Покажи память (когда пусто) | memory_empty |
| Какой мой кофе? (когда не знает) | my_coffee_unknown |
| Домой (когда адреса нет) | route_home_unknown |
| Забудь кофе (когда нет) | delete_not_found |
| Что ты обо мне знаешь? (когда пусто) | about_me_empty |