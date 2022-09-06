DROP TABLE IF EXISTS `user`;
DROP TABLE IF EXISTS `room`;
DROP TABLE IF EXISTS `room_member`;

CREATE TABLE `user` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(255) NOT NULL,
  `token` VARCHAR(255) NOT NULL,
  `leader_card_id` INT UNSIGNED NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token` (`token`)
);

CREATE TABLE `room` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `room_id` BIGINT UNSIGNED NOT NULL,
  `live_id` INT UNSIGNED NOT NULL,
  `max_user_count` INT UNSIGNED NOT NULL,
  `status` INT UNSIGNED NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `room_id` (`room_id`)
);

CREATE TABLE `room_member` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `room_id` BIGINT UNSIGNED NOT NULL,
  `user_id` BIGINT NOT NULL,
  `live_difficulty` INT UNSIGNED NOT NULL,
  `is_owner` BOOLEAN NOT NULL,
  `is_end` BOOLEAN NOT NULL,
  `score` BIGINT UNSIGNED NOT NULL,
  `judge` VARCHAR(255) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `room_id` (`room_id`, `user_id`)
);
