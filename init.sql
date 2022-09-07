DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `token` varchar(255) NOT NULL,
  `leader_card_id` int NOT NULL,
  `room_id` bigint DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token` (`token`)
);
DROP TABLE IF EXISTS `rooms`;
CREATE TABLE `rooms` (
  `room_id` bigint not null auto_increment,
  `status` int default 1,
  `live_id` int not null,
  `j_usr_cnt` int default 1,
  `m_usr_cnt` int default 4,
  `hst_id` int not null,
  `users` text,
  `r_res_cnt` int default 0,
  PRIMARY KEY (`room_id`)
);