import java.util.Random;
import java.util.Scanner;

public class Fight {
	
	boolean loop;
	
	int dodge;
	
	Scanner scanner = new Scanner(System.in);
	
	Random r = new Random();
	
	int input;
	
	
	public void fight(GameObject player, GameObject enemy){
		loop = true;
		while(loop){
			
		System.out.println("HP: " + player.hp);
		System.out.println("Enemy HP: " + enemy.hp);
		System.out.println("Hit: 1");
		System.out.println("Try to dodge: 2");
		input = scanner.nextInt();
		
		dodge = r.nextInt(enemy.dodgeChance) + 1;
		
		if(input == 1){
			if(dodge == 2){
				System.out.println("The " + enemy.name + " dodged your attack!");
			}else{
				enemy.hp -= player.dmg;
				System.out.println(enemy.name + " took " + player.dmg + " damage!");
			}
			
		}else if(input == 2){
			if(r.nextInt(player.dodgeChance)+1 == 1){
				System.out.println("You dodged!");
			}else{
				player.hp -= enemy.dmg;
				System.out.println(enemy.name + " dealt " + enemy.dmg + " damage to you!");
			}
		}
		
		if(player.hp<=0){
			System.out.println("You died!");
			loop = false;
		}else if(enemy.hp <= 0){
			System.out.println("You killed the enemy!");
			loop = false;
		}
		}
		
	}
	
}
