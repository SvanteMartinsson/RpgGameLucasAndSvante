import java.util.Scanner;

public class Store {

	String[] itemList = new String[4];
	Scanner scanner = new Scanner(System.in);

	int itemId = 0;
	int buy;
	Player player;

	public Store(Player player){
		this.player = player;
	}

	public void initItems(){
		itemList[0] = "Hp potion";
		itemList[1] = "Sword";
		itemList[2] = "Axe";
		itemList[3] = "Longsword";
	}

	public void buyItems(){
		System.out.println("Welcome to the store!");
		System.out.println("-------------------------------");
		for(int i = 0; i<=3; i++){
			System.out.println(i+1 + ": " + itemList[i]);
		}
		System.out.println("-------------------------------");
		buy = scanner.nextInt();
		if(buy == 1 && player.gold >= 65){
			player.gold -= 65;
			player.hp = player.maxHp;
		}else if(buy == 2 && player.gold >= 100){
			player.gold -=50;
			player.newWeapon(1);
		}else if(buy == 3 && player.gold >= 175){
			player.gold -=175;
			player.newWeapon(2);
		}else if(buy == 4 && player.gold >= 350){
			player.gold -= 350;
			player.newWeapon(3);
		}

	}

}
