DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) DEFAULT NULL,
  `token` varchar(255) DEFAULT NULL,
  `leader_card_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token` (`token`)
);

DROP TABLE IF EXISTS `room`;
CREATE TABLE `room` (
  `room_id` bigint NOT NULL AUTO_INCREMENT,
  `live_id` bigint NOT NULL,
  `joined_user_count` int NOT NULL,
  `max_user_count` int NOT NULL DEFAULT 4,
  `status` int NOT NULL DEFAULT 1,
  PRIMARY KEY (`room_id`)
);

-- TODO: 外部キー制約を貼る
DROP TABLE IF EXISTS `room_member`;
CREATE TABLE `room_member` (
  `room_id` bigint NOT NULL,
  `user_id` bigint NOT NULL,
  `select_difficulty` int NOT NULL,
  `is_host` boolean NOT NULL,
  `score` int,
  `judge` varchar(255),
  PRIMARY KEY (`room_id`, `user_id`)
);

-- testデータ
-- INSERT INTO `user` SET `name`='a', `token`='2f4f9beb-1d8b', `leader_card_id`=4;
-- INSERT INTO `room` SET `live_id`=1001, `joined_user_count`=1, `max_user_count`=4;
-- INSERT INTO `room` SET `live_id`=1002, `joined_user_count`=0, `max_user_count`=4; 
-- INSERT INTO `room_member` SET `room_id`=1, `user_id`=1, `select_difficulty`=1,`is_host`=1