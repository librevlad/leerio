# LEERIO — OPERATING SYSTEM

## ROLE

Senior product engineer. Уровень: AIMP / Spotify.

Приоритет:

1. Stability — playback никогда не ломается
2. UX — 1 клик до воспроизведения
3. Performance — мгновенный отклик
4. Simplicity — минимум кода и UI

НЕ добавлять фичи без запроса. НЕ переписывать рабочий код. НЕ усложнять.

---

# CORE FLOW (СВЯЩЕННЫЙ)

```
Открыл → Continue Listening → 1 клик → играет → autoplay next
```

Любое изменение НЕ должно ломать этот flow. Без исключений.

Гарантии:

* Resume ≤ 1 клик
* Start ≤ 1 секунда
* Pause — мгновенный
* Seek — точный
* Track switch — без лагов
* Position — никогда не теряется

---

# AUDIO ENGINE CONTRACT

Single source of truth — `usePlayer.ts` singleton:

* `currentBook`, `currentTrack`, `currentTrackIndex`
* `isPlaying`, `isLoading`, `currentTime`, `duration`
* `audioError`, `playingOffline`

Правила:

* 1 Audio instance (singleton, `ensureAudio()`)
* UI синхронизирован через Vue refs ← audio events
* Operation ID pattern: `loadOpId` / `playOpId` отменяют stale async операции
* Position: localStorage (instant) + API (async) — dual-layer persistence
* Preload: URL следующего трека кэшируется после каждого `playTrack`

Race condition защита:

* `loadBook` — `loadOpId` counter, staleness check после каждого await
* `playTrack` — `playOpId` counter, staleness check после resolveAudioSrc
* `preloadNextTrack` — проверка что книга не сменилась
* Concurrent `loadBook` вызовы — предыдущий отменяется автоматически

Error handling:

* Аудио не загрузилось → `audioError = true` + retry/skip UI
* Сеть пропала → localStorage fallback для position, SW cache для audio
* Файл битый → `skipErrorTrack()` → следующий трек

---

# OFFLINE-FIRST

* Приложение работает без сети
* Синхронизация — фоновая
* Никакие действия не блокируются сетью
* Аудио: SW cache (50 entries, 7 days) → downloads (native) → IndexedDB (local books)
* Position: localStorage (всегда) + API (когда есть сеть)
* Mutations: localStorage queue → replay on reconnect

---

# DEVELOPMENT MODE

5 этапов. Всегда. Без исключений.

## 1. UNDERSTANDING

* Что реализовано? Где в коде? Какие данные?

## 2. ARCHITECTURE

* Data flow, state, API, edge cases
* НЕ ПИШИ КОД на этом этапе

## 3. IMPLEMENTATION

* Строго по плану
* Существующие паттерны
* Минимальные изменения

## 4. UX REVIEW

* Сколько кликов? Есть задержка? Где путаница?

## 5. QA

* Баги, edge cases, race conditions, offline

---

# BUGFIX MODE

1. Root cause (не симптом)
2. Системное исправление (не костыль)
3. Проверить что не сломал другое
4. Если async — проверить race conditions

---

# DESIGN SYSTEM

## Layout

* Минимум элементов на экране
* 1 главный action на экран
* Макс. 3 уровня вложенности
* Крупные отступы (px-4/px-6, py-3/py-4 minimum)
* Строгая сетка

## Typography

* Заголовки: `text-[18px]`–`text-[20px]` font-bold
* Основной текст: `text-[13px]`–`text-[14px]`
* Мелкий: `text-[11px]`–`text-[12px]` text-[--t3]
* Максимум 2–3 размера на экран

## Colors

* Основной: `--t1` (белый/светлый текст)
* Акцент: `--accent` / `--gradient-accent` (оранжевый)
* Нейтральный: `--t2`, `--t3` (серые)
* Фон: `--bg`, `--card`, `--card-solid`
* Не добавлять новые цвета

## Components

* `card` — стандартная карточка
* `btn-primary` — главная кнопка
* `section-label` — заголовок секции
* `page-title` — заголовок страницы
* Не создавать новые компоненты без причины

---

# UX RULES

* Resume playback ≤ 1 клик
* Start playback ≤ 1 секунда
* Никаких пустых состояний — всегда skeleton или контент
* Никаких "мертвых" кнопок
* Всегда понятен следующий шаг
* Пользователь всегда знает: что играет, где он, что дальше

ЗАПРЕЩЕНО:

* Лишние экраны и модалки
* Лишние клики
* Блокирующие загрузки
* UI ради UI
* Декоративные элементы без функции

---

# SCREENS

## Home (Dashboard)

Цель: продолжить слушать за 1 клик.

* Continue Listening (приоритет)
* Рекомендации / trending
* Активность

## Player (Fullscreen)

Цель: только playback controls.

* Обложка + info
* Seek bar + time
* Play/pause + prev/next + skip
* Speed, sleep, bookmark, volume
* Track list

## Library

Цель: найти книгу.

* Поиск + фильтры
* Карточки книг

## Book Detail

Цель: начать слушать.

* Info + cover
* Кнопка "Слушать" (1 main action)
* Оглавление

---

# EXISTING FEATURES (НЕ УДАЛЯТЬ)

* offline playback (IndexedDB + SW cache)
* sync система (offline queue)
* аналитика
* коллекции
* заметки / закладки
* user books (загрузка своих книг)

Не ломать. Не переписывать без причины.

---

# WHAT NOT TO TOUCH

* collections
* notes / quotes
* аналитика
* если задача не требует → не трогать

---

# PERFORMANCE

* Не блокировать UI
* Минимизировать ререндеры
* Preload где возможно
* Skeleton вместо пустого экрана
* Lazy load для тяжелых компонентов

---

# CODE RULES

ПИШИ:

* Простой код, минимальный state, понятные функции
* Operation ID pattern для async операций
* Guard clauses вместо глубокой вложенности

НЕ ПИШИ:

* Абстракции без причины
* Дублирование state
* Сложные паттерны без необходимости
* Код "на будущее"

---

# TESTING

Перед завершением:

1. Core flow: открыть → continue → слушать
2. Offline: работает без сети
3. Position: сохраняется и восстанавливается
4. Race conditions: быстрые клики, смена треков
5. Unit tests: `vitest run`
6. Type check: `vue-tsc --noEmit`
7. Lint: `eslint`

E2E стресс-тесты (`player-stress.spec.ts`):

* Spam play/pause 20x
* Fast track switch 10x
* Seek stress
* Reload persistence
* Offline fallback
* Slow network

---

# ANTI-PATTERNS

ЗАПРЕЩЕНО:

* Делать "на будущее"
* Добавлять фичи без запроса
* Переписывать рабочий код
* Усложнять архитектуру
* Лишние элементы в UI
* Дублирование state
* `any` без eslint-disable

---

# DEFINITION OF DONE

Задача НЕ завершена если:

* Есть баги
* UX не мгновенный
* Есть race conditions
* Есть лаги или зависания
* Не работает offline
* Сломан core flow
* Не пройдены тесты

---

# DECISION RULE

Если сомневаешься → выбирай самое простое решение, которое работает.

---

# GOAL

Не "написать код". Построить:

* Стабильное как AIMP
* Простое как Spotify
* Без багов, без лишнего UI
* Идеальный UX прослушивания
