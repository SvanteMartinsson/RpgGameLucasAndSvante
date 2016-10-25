import java.util.Random;
import java.util.Scanner;

public class Fight {

	boolean loop;
	
	int loot;

	int eChoise = 0;

	Scanner scanner = new Scanner(System.in);

	Random r = new Random();

	int input;

	public void playerAttack(GameObject player, GameObject enemy){
		if(input == 1){
			if(r.nextInt(100 + 1) >= 70){
				enemy.hp -= player.dmg*2;
				System.out.println("You did "+ player.dmg*2 + " damage to " + enemy.name + "!");
			}else{
				System.out.println("You missed!");
			}

		}else if(input == 2){
			if(r.nextInt(100 + 1) >= 45){
				enemy.hp -= player.dmg*1.5;
				System.out.println("You did "+ player.dmg*1.5 + " damage to " + enemy.name + "!");
			}else{
				System.out.println("You missed!");
			}

		}else if(input == 3){
			if(r.nextInt(100 + 1) >= 25){
				enemy.hp -= player.dmg;
				System.out.println("You did "+ player.dmg + " damage to " + enemy.name + "!");
			}else{
				System.out.println("You missed!");
			}
		}
	}

	public void enemyAttack(GameObject player, GameObject enemy){

		eChoise = r.nextInt(3) + 1;

		if(eChoise == 1){
			if(r.nextInt(100 + 1) >= 70){
				player.hp -= enemy.dmg*2;
				System.out.println(enemy.name + " did " + enemy.dmg*2 + " damage to you!");
			}else{
				System.out.println(enemy.name + " missed!");
			}
		}else if(eChoise == 2){
			if(r.nextInt(100 + 1) >= 45){
				player.hp -= enemy.dmg*1.5;
				System.out.println(enemy.name + " did " + enemy.dmg*1.5 + " damage to you!");
			}else{
				System.out.println(enemy.name + " missed!");
			}
		}else if(eChoise == 3){

			if(r.nextInt(100 + 1) >= 25){
				player.hp -= enemy.dmg;
				System.out.println(enemy.name + " did " + enemy.dmg + " damage to you!");
			}else{
				System.out.println(enemy.name + " missed!");
			}
		}
	}


	public void fight(GameObject player, GameObject enemy){
		loop = true;
		
		System.out.println("You encounter a " + enemy.name);
		
		while(loop){
			loot = 0;
			System.out.println("HP: " + player.hp);
			System.out.println("Enemy HP: " + enemy.hp);
			System.out.println("Power attack(30%): 1");
			System.out.println("Normal attack(55%): 2");
			System.out.println("Quick attack(75%): 3");
			input = scanner.nextInt();


			playerAttack(player, enemy);
			enemyAttack(player, enemy);

			if(player.hp<=0){
				System.out.println("You died!");
				player.hp = player.maxHp;
				enemy.hp = enemy.maxHp;
				
				loop = false;
			}else if(enemy.hp <= 0){
				System.out.println("You killed the enemy!");
				//player.hp = player.maxHp;
				enemy.hp = enemy.maxHp;
				player.xp += enemy.lvl*5;
				if(enemy.lvl == 1){
					loot += r.nextInt(6) + 3;
					System.out.println("You got " + loot + " gold.");
					player.gold += loot;
				}else if(enemy.lvl == 2){
					loot += r.nextInt(18) + 14;
					System.out.println("You got " + loot + " gold.");
					player.gold += loot;
				}else if(enemy.lvl == 3){
					loot += r.nextInt(22) + 18;
					System.out.println("You got " + loot + " gold.");
					player.gold += loot;
				}
				
				loop = false;

			}
		}
	}

}
