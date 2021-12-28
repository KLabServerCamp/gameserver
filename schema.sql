DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) DEFAULT NULL,
  `token` varchar(255) DEFAULT NULL,
  `leader_card_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token` (`token`)
);

INSERT INTO user(id,name,token,leader_card_id) VALUES (0,'ほのか','asdfghjkl','12345');
INSERT INTO user(id,name,token,leader_card_id) VALUES (0,'ことり','zxcv','88998');
INSERT INTO user(id,name,token,leader_card_id) VALUES (0,'うみ','qwert','173248');

INSERT INTO user
  (id,name,token,leader_card_id)
VALUES 
  (0,'ほのか','asdfghjkl','12345'),
  (0,'ことり','zxcv','88998'),
  (0,'うみ','qwert','173248');

SELECT * FROM user WHERE name='うみ';

SELECT * FROM user WHERE name LIKE 'ほ%';
