
public class Player extends GameObject{

	String[] inv = new String[14];
	int invSpot;
	int lastSpot = 0;
	
	public Player(int hp, int dmg, String name, String sex){
		this.hp = hp;
		this.dmg = dmg;
		this.name = name;
		this.sex = sex;
	}
	
	public void attack() {
		
		
	}
	
	public void addToInv(String item){
		inv[lastSpot] = item;
		lastSpot++;
	}
	
	public void deleteFromInv(){
		inv[lastSpot] = " ";
	}
	
	public void displayInv(){
		
		// Displays the inventory with place number
		for(int i = 0; i<lastSpot; i++){
			invSpot = i+1;
			
			System.out.println(i+1 + " " + inv[i]);
			
		}
	}

}
