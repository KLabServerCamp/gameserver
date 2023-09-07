use webapp;

-- DROP TABLE IF EXISTS `user`;
-- CREATE TABLE `user` (
--   `id` bigint NOT NULL AUTO_INCREMENT,
--   `name` varchar(255) NOT NULL,
--   `token` varchar(255) NOT NULL,
--   `leader_card_id` int NOT NULL,
--   PRIMARY KEY (`id`),
--   UNIQUE KEY `token` (`token`)
-- );

DROP TABLE IF EXISTS `room`;
CREATE TABLE `room` (
  `room_id` bigint NOT NULL AUTO_INCREMENT,
  `live_id` bigint NOT NULL,
  `selected_difficulty` int NOT NULL,
  `joined_user_count` int DEFAULT 1 NOT NULL,
  `max_user_count` int DEFAULT 4 NOT NULL,
  PRIMARY KEY (`room_id`)
);

DROP TABLE IF EXISTS `room_member`;
CREATE TABLE `room_member` (
  `room_id` bigint NOT NULL,
  `member1` bigint NOT NULL,
  `member2` bigint,
  `member3` bigint, 
  `member4` bigint,
  PRIMARY KEY (`room_id`),
  UNIQUE KEY `room_id` (`room_id`)
);